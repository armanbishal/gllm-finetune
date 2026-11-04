# prompts

Each prompt has two files: a system message and a user message.

| prefix | role | what it asks for |
|--------|------|------------------|
| `prompt_00` | baseline | solve the task and pass the test cases |
| `prompt_04` | efficiency | same, plus explicit rules for optimal time/space, built-ins, single-pass, in-place |

Usage: read `<prefix>_system.txt` as the system message and `<prefix>_user.txt`
as the user message, then append the actual task description and test cases to
the user message before sending it to the model.
