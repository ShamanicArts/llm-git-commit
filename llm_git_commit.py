import click
import llm # Main LLM library
import subprocess # For running git commands
from prompt_toolkit import PromptSession # For interactive editing
from prompt_toolkit.patch_stdout import patch_stdout # Important for prompt_toolkit
# from prompt_toolkit.lexers import PygmentsLexer # Optional: if you want syntax highlighting
# from pygments.lexers.text import PlainTextLexer   # for the commit message editor

# --- System Prompt ---
DEFAULT_GIT_COMMIT_SYSTEM_PROMPT = """
You are an expert programmer tasked with writing a git commit message.
Based on the provided 'git diff' output, generate a concise and informative commit message.
The commit message should ideally follow the Conventional Commits specification (e.g., 'feat: add new login button', 'fix: resolve issue with user authentication', 'docs: update API documentation', 'style: reformat code according to style guide', 'refactor: improve performance of data processing module', 'test: add unit tests for new service', 'chore: update dependencies').
The diff output shows only the changes to be committed.

Focus on describing WHAT changed and WHY the change was made, if apparent from the diff.
Keep the subject line (the first line) ideally under 50 characters. If more detail is needed, provide a blank line after the subject and then a more detailed body.

Output ONLY the raw commit message. Do not include any other explanatory text, preamble, markdown formatting like '```', or any phrases like "Here's the commit message:".
"""

# --- LLM Plugin Hook ---
@llm.hookimpl
def register_commands(cli):
    """
    Registers the 'git-commit' command with the LLM CLI.
    """
    @cli.command("git-commit")
    @click.option(
        "--staged", "diff_mode", flag_value="staged", default=True,
        help="Generate commit message based on staged changes (git diff --staged). [Default]"
    )
    @click.option(
        "--tracked", "diff_mode", flag_value="tracked",
        help="Generate commit message based on all changes to tracked files (git diff HEAD)."
    )
    @click.option(
        "-m", "--model", "model_id_override", default=None,
        help="Specify the LLM model to use (e.g., gpt-4, claude-3-opus)."
    )
    @click.option(
        "-s", "--system", "system_prompt_override", default=None,
        help="Custom system prompt to override the default."
    )
    @click.option(
        "--key", "api_key_override", default=None,
        help="API key for the LLM model (if required and not set globally)."
    )
    @click.option(
        "-y", "--yes", is_flag=True,
        help="Automatically confirm and proceed with the commit without interactive editing (uses LLM output directly)."
    )
    def git_commit_command(diff_mode, model_id_override, system_prompt_override, api_key_override, yes):
        """
        Generates a Git commit message using an LLM based on repository changes,
        allows interactive editing, and then commits.
        """
        
        # 1. Check if inside a Git repository
        if not _is_git_repository():
            click.echo(click.style("Error: Not inside a git repository.", fg="red"))
            return

        # 2. Get Git diff
        diff_output, diff_description = _get_git_diff(diff_mode)

        if diff_output is None: # Error occurred in _get_git_diff
            return

        if not diff_output.strip():
            click.echo(f"No {diff_description} to commit.")
            _show_git_status()
            return

        # 3. Prepare for and call LLM
        from llm.cli import get_default_model # Import here to ensure LLM environment is ready

        actual_model_id = model_id_override or get_default_model()
        if not actual_model_id:
            click.echo(click.style("Error: No LLM model specified and no default model configured.", fg="red"))
            click.echo("Try 'llm models list' or 'llm keys set <model_alias>'. Specify with --model <model_id>.")
            return

        try:
            model_obj = llm.get_model(actual_model_id)
        except llm.UnknownModelError:
            click.echo(click.style(f"Error: Model '{actual_model_id}' not recognized.", fg="red"))
            click.echo("Try 'llm models list' to see available models.")
            return
        
        if model_obj.needs_key:
            model_obj.key = llm.get_key(api_key_override, model_obj.needs_key, model_obj.key_env_var)
            if not model_obj.key:
                click.echo(click.style(f"Error: API key for model '{actual_model_id}' not found.", fg="red"))
                click.echo(f"Set via 'llm keys set {model_obj.needs_key}', --key option, or ${model_obj.key_env_var}.")
                return

        # Truncate diff if too long (simple approach)
        MAX_DIFF_CHARS = 15000 # Adjust based on typical model context limits
        if len(diff_output) > MAX_DIFF_CHARS:
            click.echo(click.style(f"Warning: Diff is very long ({len(diff_output)} chars), truncating to {MAX_DIFF_CHARS} chars for LLM.", fg="yellow"))
            diff_output = diff_output[:MAX_DIFF_CHARS] + "\n\n... [diff truncated]"

        system_prompt = system_prompt_override or DEFAULT_GIT_COMMIT_SYSTEM_PROMPT
        
        click.echo(f"Generating commit message using {click.style(actual_model_id, bold=True)} based on {diff_description}...")
        
        try:
            response_obj = model_obj.prompt(diff_output, system=system_prompt)
            generated_message = response_obj.text().strip()
        except Exception as e:
            click.echo(click.style(f"Error calling LLM: {e}", fg="red"))
            return

        if not generated_message:
            click.echo(click.style("LLM returned an empty commit message. Please write one manually or try again.", fg="yellow"))
            generated_message = "" # Start with an empty message for editing

        # 4. Interactive Edit & Commit or Direct Commit
        if yes:
            if not generated_message:
                click.echo(click.style("LLM returned an empty message and --yes was used. Aborting commit.", fg="red"))
                return
            final_message = generated_message
            click.echo(click.style("\nUsing LLM-generated message directly:", fg="cyan"))
            click.echo(f'"""\n{final_message}\n"""')
        else:
            final_message = _interactive_edit_message(generated_message)

        if final_message is None or not final_message.strip(): # User cancelled or cleared message
            click.echo("Commit aborted.")
            return
        
        _execute_git_commit(final_message, diff_mode == "tracked")


# --- Helper Functions ---
def _is_git_repository():
    """Checks if the current directory is part of a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True, capture_output=True, text=True, cwd="."
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def _get_git_diff(diff_mode):
    """Gets the git diff output based on the specified mode."""
    diff_command = ["git", "diff"]
    if diff_mode == "staged":
        diff_command.append("--staged")
        description = "staged changes"
    elif diff_mode == "tracked":
        diff_command.append("HEAD") # Shows changes to tracked files (unstaged)
        description = "unstaged changes in tracked files"
    else: # Should not happen with click flags
        click.echo(click.style(f"Internal error: Unknown diff mode '{diff_mode}'.", fg="red"))
        return None, "unknown changes"
        
    try:
        process = subprocess.run(
            diff_command, capture_output=True, text=True, check=True, cwd="."
        )
        return process.stdout, description
    except subprocess.CalledProcessError as e:
        # If 'git diff HEAD' fails, it might be an empty repo.
        # 'git diff --staged' failing usually means no staged changes, but stdout would be empty (handled later).
        click.echo(click.style(f"Error getting git diff ({' '.join(diff_command)}):\n{e.stderr or e.stdout}", fg="red"))
        return None, description
    except FileNotFoundError:
        click.echo(click.style("Error: 'git' command not found. Is Git installed and in your PATH?", fg="red"))
        return None, description


def _show_git_status():
    """Shows a brief git status."""
    try:
        status_output = subprocess.check_output(["git", "status", "--short"], text=True, cwd=".").strip()
        if status_output:
            click.echo("\nCurrent git status (--short):")
            click.echo(status_output)
        else:
            click.echo("Git status is clean (no changes detected by 'git status --short').")
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(click.style("Could not retrieve git status.", fg="yellow"))


def _interactive_edit_message(suggestion):
    """Allows interactive editing of the commit message."""
    click.echo(click.style("\nSuggested commit message (edit below):", fg="cyan"))
    
    session = PromptSession(
        # lexer=PygmentsLexer(PlainTextLexer), # Keep it simple, or explore more specific lexers
        message="Commit message (Esc+Enter or Meta+Enter for multi-line; Ctrl-D or Ctrl-C to cancel):\n" # Prompt shown before the input area
    )
    
    with patch_stdout(): # Essential for prompt_toolkit
        edited_message = session.prompt(
            default=suggestion,
            multiline=True # Git commit messages can be multi-line
        )
    return edited_message # Returns None if Ctrl-D/Ctrl-C


def _execute_git_commit(message, commit_all_tracked):
    """Executes the git commit command."""
    commit_command = ["git"]
    action_description = "Committing"

    if commit_all_tracked:
        # 'git commit -a' stages all modified/deleted *tracked* files then commits.
        # This matches the scope of 'git diff HEAD'.
        # It does NOT add new untracked files.
        commit_command.extend(["commit", "-a", "-m", message])
        action_description = "Staging all tracked file changes and committing"
    else: # Staged changes
        commit_command.extend(["commit", "-m", message])
        action_description = "Committing staged changes"
        
    click.echo(f"\n{action_description} with message:")
    click.echo(click.style(f'"""\n{message}\n"""', fg="yellow"))
    
    if not click.confirm(f"Proceed?", default=True):
        click.echo("Commit aborted by user.")
        return

    try:
        process = subprocess.run(
            commit_command, capture_output=True, text=True, check=True, cwd="."
        )
        click.echo(click.style("\nCommit successful!", fg="green"))
        if process.stdout:
            click.echo("Git output:")
            click.echo(process.stdout)
        # stderr might contain info even on success for some git operations, or warnings
        if process.stderr:
            click.echo("Git stderr:")
            click.echo(process.stderr)
            
    except subprocess.CalledProcessError as e:
        click.echo(click.style("\nError during git commit:", fg="red"))
        output = (e.stdout or "") + (e.stderr or "")
        click.echo(output if output else "No output from git.")
    except FileNotFoundError:
        click.echo(click.style("Error: 'git' command not found.", fg="red"))
