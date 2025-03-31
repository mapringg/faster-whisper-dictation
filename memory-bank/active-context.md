# Active Context

- **Current Focus:** Updating Memory Bank to reflect the project's shift from supporting local `faster-whisper` to _exclusively_ using cloud APIs (OpenAI/Groq) based on user feedback.
- **Recent Changes:**
  - Updated `project-brief.md`, `product-context.md`, `system-patterns.md`, `tech-context.md` to reflect cloud-only transcription focus and remove references to local models/libraries.
- **Next Steps:**
  - Update `progress.md` to log the historical decision to remove local transcription.
  - Final review of Memory Bank consistency.
- **Active Decisions/Considerations:** Ensuring all documentation accurately represents the current cloud-only architecture and removes references/implications of the previous local transcription capability.
- **Key Patterns/Preferences:**
  - Environment variables are the preferred method for configuration (e.g., API keys).
  - Loading priority: Shell > Project (`./.env`) > Home (`$HOME/.env`).
- **Learnings/Insights:** The project uses a custom function (`src/core/utils.py::load_env_from_file`) for loading `.env` files.
