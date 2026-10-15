# Northwind Assistant — how to use the bot in Teams

Guide for **employees** using Northwind Assistant in Microsoft Teams (1:1 chat).

**For IT administrators:** installation and permissions — [CUSTOMER-SETUP-EN.md](CUSTOMER-SETUP-EN.md).

---

## Getting started

1. Open **Microsoft Teams** (desktop or web).
2. Click **Apps** in the left sidebar.
3. Search for **Northwind Assistant**.
4. Click **Add** or **Open**.
5. Type your question in plain language.

The bot works in **1:1 chat** only. Group chats and team channels are not supported yet.

Replies usually arrive within a few seconds to half a minute. During longer searches you may see short status messages (e.g. analyzing your question, searching documents).

---

## What you can ask

The assistant searches **internal company documentation** (contracts, instructions, procedures, annexes). Examples:

- “What are the conditions for terminating a lease?”
- “Where is the handover protocol template?”
- “How is the deposit settled?”
- “What documents are needed for a lease extension?”

Write in **Polish** (default) or English — the bot tries to match the answer language to your question.

If your question is **ambiguous** (e.g. first lease vs extension), the bot may ask **one or two clarifying questions** instead of guessing.

---

## Sources at the end of answers

Many answers end with a **Źródła** (Sources) section — file names with **clickable SharePoint links**.

| File type | What happens when you click |
|-----------|----------------------------|
| **PDF** | Opens in the browser |
| **Word, Excel, PowerPoint** | Opens in Office on the web (no download required) |

Page numbers may appear in the label; the link usually opens the **whole document**, not a single page.

Answer text does **not** include inline “Source 1” markers — citations are listed only under **Źródła**.

---

## Commands

| Command | Action |
|---------|--------|
| `/style …` | Saves **your style preferences** (e.g. `/style short, bullet points` or `/style answer in English`) |
| `/style` | Shows your current preferences |
| `/style reset` | Clears saved preferences |
| `/clean_chat_history` | Clears the bot’s **conversation history** for you (the bot “forgets” prior messages in this chat) |
| `/wyczysc_historie` | Same as `/clean_chat_history` |

**Note:** `/style` preferences are tied to **your Teams account** and **persist** after `/clean_chat_history`. Use `/style reset` to remove them.

---

## Tips

- **One topic per message** works better than a long list of unrelated questions.
- **Follow-ups** — you can say “expand on that” or “what about…?” in the same chat; the bot uses recent context.
- **Missing information** — if something is not in the documentation, the bot says so instead of inventing an answer.
- **Long answers** — often include a **Key points** / **Najważniejsze punkty** summary for easier scanning.

---

## If something goes wrong

If the bot does not reply, shows an error, or gives an clearly wrong answer:

1. Try **`/clean_chat_history`** and ask again.
2. Contact your Teams administrator or Ragstone:

- Email: contact@example.com
- Phone: +48 000 000 000

---

*Last updated: May 2026*
