"""v3.2.0: the format file — the one place for every format the owner sees.
The session start, the checks (validation-line, completion-guard, plan-guard, stats) and the replay tests read these
values from here. No other file may write its own copy of a format; a replay test fails when a text disagrees.
All text here is for the owner or the session, in ASD-STE100-lite: short sentences, common words, one word for one thing."""

# ---- closing block (end of every final answer) ----
CLOSING_LABELS = ["📌 Result:", "👉 I need from you:", "➡️ Next:"]
CLOSING_SHAPE = ("---\n"
                 "> 📌 **Result:** <where the work stands, then what works now or what I get. No requests.>\n"
                 "> 👉 **I need from you:** <one action in one short line, or \"nothing\">\n"
                 "> ➡️ **Next:** <what happens after>")
NEED_LINE_MAX_WORDS = 30
RESULT_STARTS = ["Ready to merge", "Waiting on your decision", "Still being worked on"]

# ---- validation line ----
CONFIDENCE_VALUES = ["High", "Medium", "Low"]
STATUS_VALUES = ["Proposed", "Checked", "Validated", "Uncertain"]
VALIDATION_SHAPE = "Confidence: High|Medium|Low · Status: Proposed|Checked|Validated|Uncertain"
# a short note may follow any status ("Checked — PR checked"); group 2 is the status word alone
VALIDATION_PATTERN = (r"(?m)Confidence:\s*(High|Medium|Low)\s*·\s*Status:\s*(Proposed|Checked|Validated|Uncertain)"
                      r"\b(\s*[—–\-.;:,]\s*\S.*|\s*\.)?\s*$")
VALIDATION_MEANING = ("Proposed = not checked enough. Checked = checked against the needs and known failures, and "
                      "steps walked against my setup. Validated = tested; name what ran (\"Validated — npm test "
                      "42/42\"). Uncertain = key proof is missing or in conflict. You can add a short note after "
                      "\" — \" to any status.")

# ---- decisions, completion, status ----
DECISIONS_HEADER = "❓ Decisions"   # each line names a recommendation (checked)
COMPLETION_SHAPE = "Completion: n of m done (p%)  or  Completion: Build n of m done (p%) · Check c of d"
COMPLETION_PATTERN = r"Completion:\s*(?:Build\s+)?(\d+)\s+of\s+(\d+)"
WORKING_LINE = "⏳ Working on: <names> · <n> of <m> done"
WORKING_PATTERN = r"^\s*⏳\s*Working on:\s*\S.*$"

# ---- order of a final answer ----
ANSWER_ORDER = ("Order of a final answer: first the short technical part (what changed, what you found, a regression "
                "table if needed). Then the Completion line when a plan has open items. Then the validation line. "
                "Then the \"❓ Decisions\" list, one line each, with your recommendation. Then the closing block, "
                "and nothing after it.")
CLOSING_WORDS = ("Write the three closing lines in everyday words. Use no file names, commands, code, colour codes "
                 "or sizes. Say what I will see. When the 'I need from you' line asks me to act, first send me one phone "
                 "notice with the PushNotification tool. Load it with ToolSearch.")

# ---- writing (ASD-STE100-lite) ----
STE_RULES = [
    "Start with the result: what I will see, or what changes for me. Do not explain how it works unless I ask.",
    "Use common words. Use one word for one thing. Do not change words for variety.",
    "Use these verbs: check, make sure, start, stop, use, show, find, change, remove, need.",
    "If you must use a technical word, explain it one time in plain words.",
    "Use active voice and simple tenses. Write steps as commands: \"Click Save.\"",
    "Write one instruction per sentence. Use at most 20 words in a step and 25 words in an explanation.",
    "Do not use more than 3 nouns in a row.",
    "Do not add an introduction, a repeat of my question, or a summary at the end.",
    "Do not change code, file names, commands or quotes. Accuracy is more important than style.",
]
STE_MAX_WORDS = 25

# ---- workers and helpers ----
WORKER_RUN = ("Run workers in the background. Start all workers that can run now in one step (at most 3; the "
              "plan's group tells which), then end your turn with one line: \"" + WORKING_LINE + "\". A second or "
              "third worker gets its own worktree ('Worktree:' and 'Group:' lines). The notice from each worker "
              "starts your next step. Do not wait, poll or sleep.")
REVIEWER_MOMENTS = ["before a big or risky plan", "when a worker reports \"Stuck:\"", "before every pull request",
                    "before you call the work done"]

# ---- plans ----
SQUARES = {1: "🟦", 2: "🟩", 3: "🟧", 0: "🟪"}
CHANGE_BLOCK_TITLE = "Changes in this version"          # made by the plan check, never by the model
CHANGE_BLOCK_MAX_LINES = 40
PLAN_RULES = ("Plan vN counts my approvals. Rev counts each showing inside a version and starts at Rev 1 for each "
              "version. My Approve closes the version; after it, a change is the next Plan vN; never edit the "
              "approved file. Do not write Rev marks or a change list yourself. The plan check puts the coloured "
              "square and label in front of each line changed since I last looked. It puts \"" + CHANGE_BLOCK_TITLE +
              "\" under the Summary. If it asks you to show the plan again, show it again and change nothing. "
              "Only the first showing of a new plan (Plan v1 Rev 1) has a size limit: 7,200 characters above "
              "Technical details.")
PLAN_TEMPLATE = """# Plan vN — <short plan name> — Awaiting approval

| Summary |
|---|
| What changes for you: what you will see or what will be different, in everyday words |
| What changed from the last version and why (first showing: "First version") |
| What I need to do |

<the plan itself, in everyday words; a new plan at most 7,200 characters above Technical details>

Stages to finish
<n> stages: <x> build steps by Claude, then <y> checks (<what they are>)
1. <stage> · Claude · Build · files: <main files> · after: — · level: Routine · size: S · group: A · proof: <tests, pictures or figures that show it is right>
2. <stage> · Claude · Build · files: <other files> · after: — · level: Complex · size: M · group: A · proof: <…>
3. <stage> · You · Check

Technical details: <file names, line numbers, commits, code, and any longer detail — only here>"""


def session_formats():
    """The format part of the session start, built only from the values above."""
    return "\n".join([
        "FORMATS (from the format file; the checks use the same values):",
        "Writing for me (ASD-STE100-lite): " + " ".join(STE_RULES),
        ANSWER_ORDER + " " + CLOSING_WORDS,
        "Closing block, after a line with just ---:",
        CLOSING_SHAPE,
        "The 📌 Result line starts with one of: " + " / ".join(RESULT_STARTS) + ".",
        "Validation line, one time, on its own line: " + VALIDATION_SHAPE + ". " + VALIDATION_MEANING,
        "Completion line: " + COMPLETION_SHAPE + ".",
        "Workers: " + WORKER_RUN,
        "Reviewer moments: " + "; ".join(REVIEWER_MOMENTS) + ".",
        "Plans: " + PLAN_RULES + " Write the plan in this shape:",
        PLAN_TEMPLATE,
    ])
