# Interactive Script Contract

The interactive Python script is the primary external interface. It uses `input()` to
guide the Developer and does not parse command-line arguments or flags. Human-readable
Markdown is the default analysis output.

## Startup Menu

```text
1. Analyze a change
2. Consult analysis history
3. Exit
```

The script asks for the selected option using `input()`. Invalid menu choices are
reported and the menu is shown again without terminating the session.

## Analyze a Change

```text
Codebase path: <input>
Requested change: <input>
Optional additional context: <input or blank>
Save report outside the codebase? <yes/no>
```

- The codebase path and requested change are required prompts.
- The script validates the path and requests correction when it is unavailable.
- The report is printed in the terminal and may be saved to an application-controlled
  location outside the analyzed codebase.
- The script MUST never write source artifacts below the analyzed codebase.

## Consult History

```text
1. List recent analyses
2. Search analyses
3. Open an analysis by identifier
4. Return to main menu
```

- History actions use `input()` for search text or an assessment identifier.
- Results are restricted to the current `principal_id` and show date, summary, and
  conclusion before the Developer chooses one to open.

## Error and Exit Behavior

```text
Ctrl+C: leave the current interaction without modifying the analyzed codebase
Exit: leave the application normally
```

Validation errors are explained in natural language and return to the relevant prompt.
The script does not expose command status codes as its primary interaction contract.
An unavailable or unauthorized historical assessment is presented as not found.
