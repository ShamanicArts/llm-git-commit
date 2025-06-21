import click
import llm # Main LLM library
import subprocess # For running git commands
from prompt_toolkit import PromptSession # For interactive editing
from prompt_toolkit.patch_stdout import patch_stdout # Important for prompt_toolkit
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings        
import os
import json

# ---  Configuration Management ---
# This section handles loading and saving configuration.
CONFIG_DIR = click.get_app_dir("llm-git-commit")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_MAX_CHARS = 15000

def load_config():
    """Loads configuration from the JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_config(config_data):
    """Saves configuration to the JSON file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)


# --- System Prompt (Unchanged) ---
DEFAULT_GIT_COMMIT_SYSTEM_PROMPT = """
You are an expert programmer tasked with writing a concise and conventional git commit message.
Analyze the provided 'git diff' output, which details specific code changes.
Your goal is to create a commit message that SUCCINCTLY summarizes THESE CODE CHANGES.

**Format Rules:**
1.  **Conventional Commits:** Start with a type, followed by an optional scope, a colon, and a space. Then, a short, imperative-mood description of the change.
    - Types: `feat` (new feature), `fix` (bug fix), `docs` (documentation), `style` (formatting), `refactor` (code structure), `test` (adding/improving tests), `chore` (build/tooling changes).
    - Example: `feat: add user authentication module`
    - Example: `fix(api): correct pagination error in user endpoint`
    - Example: `chore: configure linting tools`
2.  **Subject Line:** The first line (subject) MUST be 50 characters or less. It should summarize the most important aspect of the changes.
3.  **Body (Optional):**
    - If more detail is needed to explain the *what* and *why* of the code changes, add a SINGLE BLANK LINE after the subject.
    - The body should consist of one or more paragraphs. Keep these concise and focused on the changes.
    - Bullet points (using `-` or `*`) are acceptable in the body for listing multiple related changes.

**Content Guidelines - CRITICAL:**
- **Focus ONLY on the code modifications presented in the diff.**
- If the diff adds new files (e.g., a new script, module, or entire plugin), describe the *primary purpose or core functionality these new files introduce* as a collective change.
- **DO NOT:**
    - Write a project description, a general list of features of the software, or a tutorial.
    - Describe the *mere existence* of files (e.g., AVOID "Added llm_git_commit.py and pyproject.toml").
    - Be overly verbose or conversational.
    - List all functions or methods added unless they are critical to understanding the change at a high level.

**Example Scenario: Adding a new plugin (like the one you might be committing now):**
If the `git diff` output shows the initial files for a new "git-commit" plugin, a good commit message would look like this:

feat: implement initial llm-git-commit plugin

Provides core functionality for generating Git commit messages
using an LLM based on repository changes.

- Includes command structure for `llm git-commit`.
- Implements logic for retrieving git diffs (staged/tracked).
- Integrates LLM prompting for message generation.
- Adds interactive editing of suggested messages.

**Output Requirements:**
Return ONLY the raw commit message text. Do not include any explanations, markdown formatting (like '```'), or any phrases like "Here's the commit message:".
"""

# System Prompts for Chat Refinement 
CHAT_REFINEMENT_SYSTEM_PROMPT_TEMPLATE = """
You are an AI assistant helping a programmer refine a Git commit message.
The original code changes (git diff) are:
--- DIFF START ---
{original_diff}
--- DIFF END ---

The programmer's current draft of the commit message (which we are discussing) is:
--- CURRENT DRAFT START ---
{initial_commit_draft} # This will be the 'message_being_refined_in_chat' in practice for context
--- CURRENT DRAFT END ---

Engage in a conversation.
- If the user asks a question, answer it.
- If the user asks for a specific change, a rewrite, or to make something more concise, **your response should be the FULL, REVISED commit message text incorporating that change.**
- If you provide a revised commit message, ensure it adheres to conventional commit standards.
- Do not add conversational prefixes like "Okay, here's the revised message:". Just output the raw commit message if you're providing a revision.
- If just answering a question, provide only the answer.

The user can type '/accept' to make your last suggested full commit message the new current draft, or '/apply' to use the current draft for the final commit and exit.
"""

CHAT_APPLY_SYSTEM_PROMPT = """
You are an AI assistant tasked with generating a final, high-quality Git commit message.
You have been provided with:
1. The original 'git diff' output.
2. The user's initial draft of the commit message.
3. The full conversation history where the user discussed and requested refinements.

Based on ALL this information, generate a new, complete git commit message.
Adhere to conventional commit standards.
The subject line MUST be 50 characters or less.
Include a body if necessary, separated by a blank line.
Output ONLY the raw commit message text. Do not include any explanations, markdown formatting (like '```'), or any phrases like "Here's the commit message:".
"""

# --- LLM Plugin Hook ---
@llm.hookimpl
def register_commands(cli):
    """
    Registers the 'git-commit' command group with the LLM CLI.
    """
    
    @cli.group(name="git-commit", invoke_without_command=True)
    @click.pass_context
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
        "--max-chars", "max_chars_override", type=int, default=None,
        help="Set max characters for the diff sent to the LLM."
    )
    @click.option(
        "--key", "api_key_override", default=None,
        help="API key for the LLM model (if required and not set globally)."
    )
    @click.option(
        "-y", "--yes", is_flag=True,
        help="Automatically confirm and proceed with the commit without interactive editing (uses LLM output directly)."
    )
    def git_commit_command(ctx, diff_mode, model_id_override, system_prompt_override, max_chars_override, api_key_override, yes):
        """
        Generates Git commit messages using an LLM.

        Run 'llm git-commit config --help' to manage persistent defaults.
        """
       
        if ctx.invoked_subcommand is not None:
            return

        
        config = load_config()

        #  Check if inside a Git repository
        if not _is_git_repository():
            click.echo(click.style("Error: Not inside a git repository.", fg="red"))
            return

        #  Get Git diff
        diff_output, diff_description = _get_git_diff(diff_mode)

        if diff_output is None: # Error occurred in _get_git_diff
            return

        if not diff_output.strip():
            if diff_mode == "staged":
                click.echo("No staged changes found.")
                _show_git_status()
                if click.confirm("Do you want to stage all changes and commit?", default=True):
                    click.echo("Staging all changes...")
                    try:
                        subprocess.run(["git", "add", "."], check=True, cwd=".")
                        click.echo(click.style("Changes staged.", fg="green"))
                        diff_output, diff_description = _get_git_diff("staged")
                        if diff_output is None or not diff_output.strip():
                            click.echo(click.style("No changes to commit even after staging.", fg="yellow"))
                            return
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        click.echo(click.style(f"Error staging changes: {e}", fg="red"))
                        return
                else:
                    click.echo("Commit aborted.")
                    return
            else: # diff_mode is "tracked"
                click.echo(f"No {diff_description} to commit.")
                _show_git_status()
                return

        # Prepare for and call LLM
        from llm.cli import get_default_model # Import here to ensure LLM environment is ready

        
        configured_model = config.get("model")
        actual_model_id = model_id_override or configured_model or get_default_model()
        
        if not actual_model_id:
            click.echo(click.style("Error: No LLM model specified or configured.", fg="red"))
            click.echo("Try 'llm models list' or set a default with 'llm git-commit config --model <id>'.")
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

        # --- Truncate diff using the resolved max_chars value ---
        max_chars = max_chars_override or config.get("max-chars") or DEFAULT_MAX_CHARS
        if len(diff_output) > max_chars:
            click.echo(click.style(f"Warning: Diff is very long ({len(diff_output)} chars), truncating to {max_chars} chars for LLM.", fg="yellow"))
            diff_output = diff_output[:max_chars] + "\n\n... [diff truncated]"

        # --- Logic to determine the system prompt with config precedence ---
        system_prompt = system_prompt_override or config.get("system") or DEFAULT_GIT_COMMIT_SYSTEM_PROMPT
        
        click.echo(f"Generating commit message using {click.style(actual_model_id, bold=True)} based on {diff_description}...")
        
        try:
            response_obj = model_obj.prompt(diff_output, system=system_prompt)
            generated_message = response_obj.text().strip()
        except Exception as e:
            click.echo(click.style(f"Error calling LLM: {e}", fg="red"))
            return

        if not generated_message:
            click.echo(click.style("LLM returned an empty commit message. Please write one manually or try again.", fg="yellow"))
            generated_message = ""

        #  Interactive Edit & Commit or Direct Commit
        if yes:
            if not generated_message:
                click.echo(click.style("LLM returned an empty message and --yes was used. Aborting commit.", fg="red"))
                return
            final_message = generated_message
            click.echo(click.style("\nUsing LLM-generated message directly:", fg="cyan"))
            click.echo(f'"""\n{final_message}\n"""')
        else:
            final_message = _interactive_edit_message(generated_message, diff_output, model_obj)

        if final_message is None or not final_message.strip():
            click.echo("Commit aborted.")
            return
        
        _execute_git_commit(final_message, diff_mode == "tracked")

    # --- 'config' subcommand attached to the git_commit_command group ---
    @git_commit_command.command(name="config")
    @click.option("--view", is_flag=True, help="View the current configuration.")
    @click.option("--reset", is_flag=True, help="Reset all configurations to default.")
    @click.option("-m", "--model", "model_config", default=None, help="Set the default model.")
    @click.option("-s", "--system", "system_config", default=None, help="Set the default system prompt.")
    @click.option("--max-chars", "max_chars_config", type=int, default=None, help="Set the default max characters.")
    @click.pass_context
    def config_command(ctx, view, reset, model_config, system_config, max_chars_config):
        """
        View or set persistent default options for llm-git-commit.
        
        Examples:
        \b
          llm git-commit config --view
          llm git-commit config --model gpt-4-turbo
          llm git-commit config --max-chars 8000
          llm git-commit config --reset
        """
        config_data = load_config()

        if view:
            click.echo(f"Configuration file location: {CONFIG_FILE}")
            if config_data:
                click.echo(json.dumps(config_data, indent=2))
            else:
                click.echo("No configuration set.")
            return

        if reset:
            if click.confirm("Are you sure you want to reset all configurations?"):
                if os.path.exists(CONFIG_FILE):
                    os.remove(CONFIG_FILE)
                click.echo("Configuration has been reset.")
            else:
                click.echo("Reset cancelled.")
            return

        updates_made = False
        if model_config is not None:
            config_data["model"] = model_config
            click.echo(f"Default model set to: {model_config}")
            updates_made = True
        
        if system_config is not None:
            config_data["system"] = system_config
            click.echo(f"Default system prompt set.")
            updates_made = True
            
        if max_chars_config is not None:
            config_data["max-chars"] = max_chars_config
            click.echo(f"Default max-chars set to: {max_chars_config}")
            updates_made = True

        if updates_made:
            save_config(config_data)
        else:
            click.echo(ctx.get_help())


# --- Helper Functions  ---

def _format_chat_history_for_prompt(chat_history: list) -> str: # <<<< NEW HELPER (small, self-contained)
    """Formats chat history for inclusion in a prompt."""
    if not chat_history:
        return "No conversation history yet."
    return "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history])

def _is_git_repository():
    """Checks if the current directory is part of a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True, capture_output=True, text=True, cwd=".",
            encoding="utf-8", errors="ignore"
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
        diff_command.append("HEAD")
        description = "unstaged changes in tracked files"
    else:
        click.echo(click.style(f"Internal error: Unknown diff mode '{diff_mode}'.", fg="red"))
        return None, "unknown changes"
        
    try:
        process = subprocess.run(
            diff_command, capture_output=True, text=True, check=True, cwd=".",
            encoding="utf-8", errors="ignore"
        )
        return process.stdout, description
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Error getting git diff ({' '.join(diff_command)}):\n{e.stderr or e.stdout}", fg="red"))
        return None, description
    except FileNotFoundError:
        click.echo(click.style("Error: 'git' command not found. Is Git installed and in your PATH?", fg="red"))
        return None, description


def _show_git_status():
    """Shows a brief git status."""
    try:
        status_output = subprocess.check_output(
            ["git", "status", "--short"], text=True, cwd=".",
            encoding="utf-8", errors="ignore"
        ).strip()
        if status_output:
            click.echo("\nCurrent git status (--short):")
            click.echo(status_output)
        else:
            click.echo("Git status is clean (no changes detected by 'git status --short').")
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(click.style("Could not retrieve git status.", fg="yellow"))


def _interactive_edit_message(suggestion: str, original_diff: str, model_obj: llm.Model):
    """Allows interactive editing of the commit message."""
    click.echo(click.style("\nSuggested commit message (edit below):", fg="cyan"))
    
    prompt_instructions_text = """\
Type/edit your commit message below.
  - To add a NEW LINE: Press Enter.
  - To SUBMIT message: Press Esc, then press Enter.
                     (Alternatively, try Alt+Enter or Option+Enter on Mac).
  - Chat to Refine: Ctrl+I.
  - To CANCEL: Press Ctrl+D or Ctrl-C.

Commit Message:
"""
    custom_style = Style.from_dict({
        'instruction': 'ansicyan' 
    })

    formatted_instructions = FormattedText([
        ('class:instruction', prompt_instructions_text)
    ])

    kb = KeyBindings()
    
    @kb.add('c-i')
    async def _handle_chat_refine(event): # Renamed for clarity
        """Handle Ctrl+I: Open chat for refinement."""
        current_text_in_editor_buffer = event.app.current_buffer.text
        
        app_style = event.app.style # Get the current application's style

        print_formatted_text(FormattedText([
            ('bold fg:ansimagenta', "\n==> Entering Chat Mode...")
        ]), style=app_style)   
        
        # Call the async chat refinement function
        # This function handles its own click.echo UI elements for the chat interaction
        refined_message_from_chat = await _chat_for_refinement(
            current_text_in_editor_buffer,
            original_diff,
            model_obj,
            custom_style
        )

        print_formatted_text(FormattedText([
            ('bold fg:ansimagenta', "<== Exiting Chat Mode...")
        ]), style=app_style)
        


        if refined_message_from_chat is not None: 
            if refined_message_from_chat != current_text_in_editor_buffer:
                # buffer update
                event.app.current_buffer.text = refined_message_from_chat
                event.app.current_buffer.cursor_position = len(refined_message_from_chat)
            
        event.app.invalidate() # CRUCIAL: Force redraw of the main prompt UI

    session = PromptSession(
        message=formatted_instructions,
        style=custom_style,
        key_bindings=kb,
        multiline=True, 
    )
    
    with patch_stdout():
        edited_message = session.prompt(
            default=suggestion, 
            #multiline=True 
        )
    return edited_message

def _execute_git_commit(message, commit_all_tracked):
    """Executes the git commit command."""
    commit_command = ["git"]
    action_description = "Committing"

    if commit_all_tracked:
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
            commit_command, capture_output=True, text=True, check=True, cwd=".",
            encoding="utf-8", errors="ignore"
        )
        click.echo(click.style("\nCommit successful!", fg="green"))
        if process.stdout:
            click.echo("Git output:")
            click.echo(process.stdout)
        if process.stderr:
            click.echo("Git stderr:")
            click.echo(process.stderr)

        if click.confirm("Do you want to push the changes?", default=False):
            click.echo("Pushing changes...")
            try:
                subprocess.run(
                    ["git", "push"], check=True, cwd=".",
                    capture_output=True, text=True, encoding="utf-8", errors="ignore"
                )
                click.echo(click.style("Push successful!", fg="green"))
            except subprocess.CalledProcessError as e:
                click.echo(click.style(f"\nError during git push:", fg="red"))
                output = (e.stdout or "") + (e.stderr or "")
                click.echo(output if output else "No output from git push.")
            except FileNotFoundError:
                click.echo(click.style("Error: 'git' command not found.", fg="red"))
            
    except subprocess.CalledProcessError as e:
        click.echo(click.style("\nError during git commit:", fg="red"))
        output = (e.stdout or "") + (e.stderr or "")
        click.echo(output if output else "No output from git.")
    except FileNotFoundError:
        click.echo(click.style("Error: 'git' command not found.", fg="red"))


async def _chat_for_refinement(initial_commit_draft: str, original_diff: str, model: llm.Model, passed_style: Style) -> str:
    """
    Handles interactive chat with the LLM to refine a commit message.
    - initial_commit_draft: The draft when chat was first entered.
    - message_being_refined_in_chat: The current conceptual draft, updated by /accept or confirmed /apply.
                                     Displayed each turn. Content styled via 'class:instruction'.
    - LLM Response content: Plain terminal text.
    - Surrounding text/prefixes: Styled using passed_style or direct colors.
    """

    # Helper for printing FormattedText using the passed style sheet
    def print_styled(text_parts_tuples, end='\n'):
        print_formatted_text(FormattedText(text_parts_tuples), style=passed_style, end=end)

    print_styled([('bold fg:ansimagenta', "\n--- Chat Session Started ---")])
    print_styled([
        ('', "Type query, or "),
        ('bold', "/accept"), ('', " (accept LLM's last suggestion as current draft),"),
    ])
    print_styled([
        ('bold', "/apply"), ('', " (use current draft & exit), "),
        ('bold', "/cancel"), ('', " (discard chat changes & exit).")
    ])
    print_styled([('class:dim', "LLM considers original diff & the initial draft context.")])

    print_styled([('bold fg:ansiyellow', f"\nReference: Initial Draft (when chat started):")])
    for line in initial_commit_draft.splitlines():
        print_styled([('class:instruction', line)])
    print_formatted_text("---", style=passed_style)

    chat_history = []
    message_being_refined_in_chat = initial_commit_draft
    last_llm_suggestion_text = None 

    def get_current_chat_system_prompt():
        return CHAT_REFINEMENT_SYSTEM_PROMPT_TEMPLATE.format(
            original_diff=original_diff,
            initial_commit_draft=message_being_refined_in_chat
        )

    chat_input_prompt_style_dict = {'prompt': 'fg:ansimagenta'}
    chat_session_own_style = Style.from_dict(chat_input_prompt_style_dict)

    chat_session = PromptSession(
        message=FormattedText([('class:prompt', "Your Query: ")]),
        style=chat_session_own_style,
    )

    while True:
        print_styled([('bold fg:ansiyellow', f"\nCurrent Draft being refined in chat:")])
        for line in message_being_refined_in_chat.splitlines():
            print_styled([('class:instruction', line)])
        print_formatted_text("---", style=passed_style)

        try:
            with patch_stdout():
                user_query = await chat_session.prompt_async()
        except KeyboardInterrupt:
            print_styled([('fg:ansiyellow', "\nChat cancelled (Ctrl+C). Returning original draft.")])
            return initial_commit_draft
        except EOFError:
            user_query = "/cancel"
            print_styled([('class:dim', "(Ctrl+D treated as /cancel)")])

        if not user_query.strip():
            user_query = "/cancel"
            print_styled([('class:dim', "(Empty input treated as /cancel)")])

        print_styled([('bold fg:ansiblue', "You: "), ('fg:ansiwhite', user_query)])

        if user_query.lower() == "/cancel":
            print_styled([('bold fg:ansiyellow', "--- Chat Cancelled. Returning original draft. ---")])
            return initial_commit_draft

        elif user_query.lower() == "/accept":
            if last_llm_suggestion_text:
                message_being_refined_in_chat = last_llm_suggestion_text
                print_styled([('bold fg:ansigreen', "Suggestion accepted. Current draft updated.")])
                last_llm_suggestion_text = None 
                chat_history.append({"role": "user", "content": "/accept"})
                chat_history.append({"role": "assistant", "content": "(User accepted last LLM suggestion as new current draft)"})
            else:
                print_styled([('fg:ansiyellow', "No recent LLM suggestion to accept. Ask LLM to refine first.")])
            print_formatted_text("---", style=passed_style)
            continue

        elif user_query.lower() == "/apply":
            print_styled([('fg:ansicyan', "Processing /apply...")])
            apply_user_content = (
                f"Original Git Diff:\n```diff\n{original_diff}\n```\n\n"
                f"Initial Commit Draft (when chat session started):\n```\n{initial_commit_draft}\n```\n\n"
                f"Current Working Draft (basis for this /apply):\n```\n{message_being_refined_in_chat}\n```\n\n"
                f"Conversation History (leading to this /apply):\n{_format_chat_history_for_prompt(chat_history)}\n\n"
                "Based on all the above, generate the new, complete commit message. Output ONLY the raw commit message text:"
            )
            apply_prompt_messages = [
                {"role": "system", "content": CHAT_APPLY_SYSTEM_PROMPT},
                {"role": "user", "content": apply_user_content}
            ]
            try:
                response = model.chat(apply_prompt_messages) if hasattr(model, "chat") else model.prompt(apply_user_content, system=CHAT_APPLY_SYSTEM_PROMPT)
                new_commit_message_from_llm = response.text().strip()

                if not new_commit_message_from_llm:
                    print_styled([('fg:ansired', "LLM returned empty for /apply. Current draft unchanged.")])
                else:
                    print_styled([('fg:ansigreen', "LLM generated the following for /apply:")])
                    for line in new_commit_message_from_llm.splitlines():
                        print_styled([('class:instruction', line)])
                    print_formatted_text("---", style=passed_style)
                    
                    confirm_prompt_style_dict = {'prompt': 'bold fg:ansiyellow'}
                    # Use a new Style object for this temporary session's specific prompt style
                    temp_session_style = Style.from_dict(confirm_prompt_style_dict)
                    confirm_prompt_ft = FormattedText([('class:prompt', "Use this message & exit chat? (y/N): ")])
                    
                    confirmation = ""
                    with patch_stdout():
                        temp_session = PromptSession(message=confirm_prompt_ft, style=temp_session_style)
                        confirmation = await temp_session.prompt_async()

                    if confirmation.lower().strip() == 'y':
                        message_being_refined_in_chat = new_commit_message_from_llm
                        print_styled([('bold fg:ansigreen', "--- Chat Applied. Returning to editor. ---")])
                        return message_being_refined_in_chat 
                    else:
                        print_styled([('bold fg:ansiyellow', "/apply changes discarded by user. Continuing chat.")])
            except Exception as e:
                print_styled([('fg:ansired', f"Error in /apply: {e}")])
            print_formatted_text("---", style=passed_style)
            continue

        chat_history.append({"role": "user", "content": user_query})
        messages_for_llm = [{"role": "system", "content": get_current_chat_system_prompt()}] + chat_history
        
        last_llm_suggestion_text = None 
        try:
            print_styled([('fg:ansiblue class:dim', "LLM thinking...")])
            
            response = model.chat(messages_for_llm) if hasattr(model, "chat") else model.prompt(_format_chat_history_for_prompt(messages_for_llm[1:]), system=get_current_chat_system_prompt())
            llm_response_text = response.text().strip()
            
            print_styled([('bold fg:ansigreen', "LLM:")])
            if not llm_response_text:
                print_styled([('class:dim', "(LLM returned no text)")])
                chat_history.append({"role": "assistant", "content": ""})
            else:
                for line in llm_response_text.splitlines():
                    print_formatted_text(FormattedText([('', line)]), style=passed_style, end='\n')
                chat_history.append({"role": "assistant", "content": llm_response_text})
                if "\n" in llm_response_text or any(kw in llm_response_text.lower() for kw in ["feat:", "fix:", "chore:", "docs:", "refactor:"]):
                    last_llm_suggestion_text = llm_response_text
        except Exception as e:
            print_styled([('fg:ansired', f"\nLLM Error: {e}")])
            chat_history.append({"role": "assistant", "content": f"(LLM Error: {e})"})
        print_formatted_text("---", style=passed_style)