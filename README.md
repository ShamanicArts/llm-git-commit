# llm-git-commit

llm plugin to generate Git commit messages based on repository changes and interactively commit.

## Installation

This plugin requires [llm](https://llm.datasette.io/) to be installed.

you can install this plugin using llm install like so

```bash
llm install llm-git-commit
```

## Usage

https://github.com/user-attachments/assets/efa71c28-2a44-4b90-9889-3f1fbacb7507


From within a Git repository, run:

```bash
llm git-commit
```

This command will:
1.  Identify changes in your Git repository (staged changes by default).
2.  Send these changes to your configured Large Language Model.
3.  If no staged changes are found (when using the default `--staged` option), you will be prompted to stage all changes before proceeding.
4.  Present the LLM-generated commit message for you to review and edit.

**Interactive Editing:**
-   You can edit the suggested message.
-   Press `Enter` to add a new line within the message.
-   To **submit** the message and proceed to commit, press `Esc` then `Enter`.
-   To **cancel**, press `Ctrl+C` or `Ctrl+D`.

After submitting the message (or if using `-y`), you'll get a final confirmation before `git commit` is executed.
After a successful commit, you will be asked if you want to push the changes (default is no).

### Options

-   `--staged`: (Default) Uses staged changes (`git diff --staged`).
-   `--tracked`: Uses all changes to tracked files (`git diff HEAD`). Commits with `git commit -a`.
-   `-m MODEL_ID`, `--model MODEL_ID`: Specify which LLM model to use.
-   `-s SYSTEM_PROMPT`, `--system SYSTEM_PROMPT`: Use a custom system prompt.
-   `-y`, `--yes`: Skip interactive editing and use the LLM's suggestion directly (still asks for final commit confirmation).

## The System Prompt

The plugin uses a specific system prompt to guide the LLM in generating commit messages. Here's the default:

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

## Development

To set up this plugin locally for further development:

1.  Ensure you have the project code in a local directory.
2.  It's recommended to use a Python virtual environment:
    ```bash
    cd path/to/your/llm-git-commit
    python3 -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # .\venv\Scripts\activate  # On Windows
    ```
3.  Install the plugin in editable mode along with its dependencies (including `llm` itself if not in the venv):
    ```bash
    pip install -e .
    ```
    Now you can modify the code, and the changes will be live when you run `llm git-commit`.

---
