# llm-git-commit

llm plugin to generate Git commit messages based on repository changes and interactively commit.

## 🐍 Installation

This plugin requires [llm](https://llm.datasette.io/) to be installed.

you can install this plugin using llm install like so

```bash
llm install llm-git-commit
```

<details>
<summary>❄️ NixOS installation via flakes</summary>
Add the llm-git-commit repo as a flake input:
nix{
    inputs = {
        llm-git-commit = {
            url = "github:ShamanicArts/llm-git-commit";
            inputs.nixpkgs.follows = "nixpkgs";
        };
    };
}
Add lines defining a Python environment for llm using a let in statement and create a wrapper script:
nix{
  pkgs,
  inputs,
  config,
  ...
}: let
  llm-git-commit = inputs.llm-git-commit.packages.${pkgs.system}.default;
  pyWithLlm = (
    pkgs.python3.withPackages (ps: [ps.llm ps.llm-mistral llm-git-commit ps.llm-openrouter])
  );
  llm-with-plugins = (
    pkgs.writeShellScriptBin "llm" ''
      exec ${pyWithLlm}/bin/llm "$@"
    ''
  );
in {
Add the llm-with-plugins wrapper package to package list:
nix  environment.systemPackages = with pkgs; [
    llm-with-plugins
  ];
Then rebuild your system, and run llm as you would normally.
</details>

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

**Interactive Commit Message Editing and Refinement:**
The plugin provides a powerful interactive interface for reviewing, editing, and refining the LLM-generated commit message.

-   **Initial Editing:** You can directly edit the suggested message.
    -   To add a NEW LINE: Press `Enter`.
    -   To SUBMIT message: Press `Esc`, then `Enter` (or `Alt+Enter`/`Option+Enter`).
    -   To CANCEL: Press `Ctrl+C` or `Ctrl+D`.

-   **Interactive Chat Refinement (Ctrl+I):**
    *   During the initial editing phase, press `Ctrl+I` to enter a dedicated chat mode.
    *   In this mode, you can converse with the LLM to iteratively refine the commit message.
    *   **How it works:**
        1.  Type your queries, feedback, or additional instructions to the LLM.
        2.  The LLM will respond conversationally and may propose a new version of the commit message.
        3.  If the LLM proposes a new message, you will be prompted to accept (Y) or reject (N) it. Accepting updates the current draft.
        4.  The chat continues until you decide to finalize the message.
    *   **Chat Mode Commands:**
        -   `/apply` or `Ctrl+A`: Use the current draft of the commit message and exit chat mode, returning to the main editor.
        -   `/cancel`: Discard any changes made in the chat session and exit, returning the message as it was when you entered chat mode.

After submitting the message (or if using `-y`), you'll get a final confirmation before `git commit` is executed.
After a successful commit, you will be asked if you want to push the changes (default is no).

### Options

-   `--staged`: (Default) Uses staged changes (`git diff --staged`).
-   `--tracked`: Uses all changes to tracked files (`git diff HEAD`). Commits with `git commit -a`.
-   `-m MODEL_ID`, `--model MODEL_ID`: Specify which LLM model to use.
-   `-s SYSTEM_PROMPT`, `--system SYSTEM_PROMPT`: Use a custom system prompt.
-   `-y`, `--yes`: Skip interactive editing and use the LLM's suggestion directly (still asks for final commit confirmation).
-   `--char-limit`: Set a character limit for the generated commit message subject line. Defaults to 50.

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

## Configuration

You can configure `llm-git-commit` using `llm`'s configuration system. This allows you to set default values for options like the model, system prompt, and character limit.

To open your `llm` configuration file, run:

```bash
llm config path
```

Then, edit the `config.json` file (or `config.yaml` if you prefer YAML) to add a `llm-git-commit` section. For example:

```json
{
    "plugins": {
        "llm-git-commit": {
            "default_model": "gpt-4",
            "default_system_prompt": "You are a helpful assistant...",
            "default_char_limit": 72
        }
    }
}
```

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
