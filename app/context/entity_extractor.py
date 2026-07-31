import re


class EntityExtractor:
    """
    Extracts entities from a user prompt.

    This is intentionally simple for V1.
    Later versions may use an LLM or NLP model.
    """

    def extract(
        self,
        prompt: str,
    ) -> str | None:
        """
        Extract the primary entity from the prompt.
        """

        patterns = [
            r"tell me about\s+(.+)",
            r"who is\s+(.+)",
            r"what is\s+(.+)",
            r"explain\s+(.+)",
        ]

        prompt = prompt.strip()

        for pattern in patterns:

            match = re.search(
                pattern,
                prompt,
                flags=re.IGNORECASE,
            )

            if match:
                entity = match.group(1).strip()

                entity = entity.rstrip("?.!,").strip().title()

                return entity.strip().title()

        return None