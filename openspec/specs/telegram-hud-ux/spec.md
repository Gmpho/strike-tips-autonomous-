# telegram-hud-ux Specification

## Purpose
TBD - created by archiving change telegram-rich-formatting. Update Purpose after archive.

## Requirements

### Requirement: Active Typing Indicator Loop
The Telegram bot MUST emit `sendChatAction("typing")` every ~4 seconds while an inbound AI request is processing in both webhook (`modal_app.py`) and polling (`channels/telegram.py`) paths, terminating cleanly when the reply is dispatched or timed out.

#### Scenario: User sends an AI chat query
Given an authorized user sends a chat message to the Telegram bot
When the request is being processed by the AI model pipeline
Then the bot repeatedly sends the "typing" action every ~4 seconds until the response is dispatched.

### Requirement: Robust HTML Formatting
The shared Telegram formatter MUST convert Markdown elements (`**bold**`, `*bold*`, `_italic_`, `` `code` ``, ```` ```pre``` ````, `> blockquote`, `# Headers`, `- bullets`) to valid Telegram HTML, escaping reserved HTML characters (`&`, `<`, `>`) so entity parse errors never occur.

#### Scenario: AI response contains markdown and unclosed symbols
Given an AI response containing markdown tags, apostrophes, and HTML special characters
When `markdown_to_telegram_html` formats the response
Then all special HTML characters are escaped and markdown tags are safely converted to Telegram HTML tags without parse exceptions.

### Requirement: Monospace Race Card Table Formatting
Pasted race cards containing race details and runner rows MUST be formatted into structured emoji headers and monospace `<pre>` alignment tables displaying runner number, horse name, decimal odds, and form summary.

#### Scenario: User pastes a 10-runner Greyville race card
Given a user pastes a text race card with course name, race number, off time, and 10 runner rows
When `format_race_card_for_telegram` processes the text
Then it outputs an emoji track header followed by a formatted monospace `<pre>` alignment table with all 10 horses.

### Requirement: Paragraph-Boundary Chunking
Outbound Telegram responses exceeding 3800 characters MUST be split at paragraph (`\n\n`) or newline (`\n`) boundaries into clean sequential messages rather than truncating mid-sentence.

#### Scenario: Long analysis response
Given an AI analysis text exceeding 3800 characters
When `split_for_telegram` chunks the text
Then the text is divided into paragraph-aligned chunks each under 3800 characters.
