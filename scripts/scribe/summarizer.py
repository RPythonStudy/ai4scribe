from google import genai
import os
from dotenv import load_dotenv

class Summarizer:
    def __init__(self, api_key=None, model_name=None):
        load_dotenv()
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is not set in environment variables or provided.")
        
        # Priority: Argument > Env Var > Default
        self.model_name = model_name or os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        
        self.client = genai.Client(api_key=self.api_key)
        self.current_summary = ""  # Store the running summary
        print(f"Summarizer initialized with model: {self.model_name}")

    def reset(self):
        """Reset the accumulated summary context."""
        self.current_summary = ""
        print("Summary context reset.")

    def summarize(self, text, meeting_title=None, user_notes=None):
        """
        Summarize the provided text using Gemini.
        If previous summary exists, it performs an incremental update.
        """
        if not text or len(text.strip()) == 0:
            return {"summary": self.current_summary, "usage": None}

        print("Summarizing text (Incremental)...")
        
        # Prepare title string
        title_str = meeting_title if meeting_title else "General Meeting"
        
        # Prepare User Notes Section
        notes_section = ""
        if user_notes and len(user_notes) > 0:
            notes_section = "\n\n📝 **Human Scribe Notes (HIGH PRIORITY - USE AS GUIDE):**\n"
            for note in user_notes:
                notes_section += f"- {note}\n"
            notes_section += "\n(End of Human Notes)\n"
        
        if self.current_summary:
            prompt_template = os.getenv(
                "GEMINI_INCREMENTAL_PROMPT",
                "Here is the summary of the meeting so far:\n{current_summary}\n\n"
                "Meeting Title: {meeting_title}\n\n"
                "{notes_section}"
                "Here is the new transcript segment:\n{text}\n\n"
                "Please update the summary to incorporate the new information while keeping the previous key points concise. "
                "Maintain a coherent flow."
            )
            # Use safe formatting or string concatenation to avoid KeyErrors with Env vars
            prompt = (f"Here is the summary of the meeting so far:\n{self.current_summary}\n\n"
                      f"Meeting Title: {title_str}\n\n"
                      f"{notes_section}"
                      f"Here is the new transcript segment:\n{text}\n\n"
                      "**Task**: Update the meeting minute.\n"
                      "**Instructions**:\n"
                      "1. Incorporate new information.\n"
                      "2. **Pay close attention to the Human Scribe Notes** above. They indicate important decisions, corrections, or speaker identities.\n"
                      "3. Keep the output in Korean.")
        else:
            prompt = (f"Meeting Title: {title_str}\n\n"
                      f"{notes_section}"
                      f"Please provide a concise context-aware summary of the following transcription:\n\n{text}\n\n"
                      "**Instructions**:\n"
                      "1. Create a structured summary.\n"
                      "2. **Reflect any Human Scribe Notes** in the summary as verified facts.")


        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            # Extract token usage
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0
            total_tokens = usage.total_token_count if usage else 0
            
            # Calculate cost (Gemini 1.5 Flash pricing: Input $0.075/1M, Output $0.30/1M)
            # Note: Pricing may vary based on specific model version and region.
            input_price = float(os.getenv("GEMINI_INPUT_PRICE_PER_1M", 0.075))
            output_price = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_1M", 0.30))
            
            input_cost = (input_tokens / 1_000_000) * input_price
            output_cost = (output_tokens / 1_000_000) * output_price
            total_cost = input_cost + output_cost
            
            print(f"Usage: Input {input_tokens}, Output {output_tokens}, Cost ${total_cost:.6f}")

            # Update the running summary
            self.current_summary = response.text

            return {
                "summary": self.current_summary,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": total_cost,
                    "currency": "USD"
                }
            }
        except Exception as e:
            return {"summary": f"Error during summarization: {e}", "error": str(e)}

    def _calculate_cost(self, input_tokens, output_tokens):
        input_price = float(os.getenv("GEMINI_INPUT_PRICE_PER_1M", 0.075))
        output_price = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_1M", 0.30))
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        return input_cost + output_cost

    def analyze_audio(self, audio_path, meeting_title=None, user_notes=None):
        """
        Uploads an audio file to Gemini and generates a structured meeting minute.
        """
        print(f"Uploading audio file: {audio_path}")
        try:
            # 1. Upload the file to Gemini
            mime_type = "audio/mp3"
            if audio_path.lower().endswith(".webm"):
                mime_type = "audio/webm"
            elif audio_path.lower().endswith(".wav"):
                mime_type = "audio/wav"
            elif audio_path.lower().endswith(".m4a"):
                mime_type = "audio/mp4"

            with open(audio_path, "rb") as f:
                audio_file = self.client.files.upload(file=f, config={'mime_type': mime_type})
            print(f"File uploaded. URI: {audio_file.uri} (MIME: {mime_type})")

            # 2. Prepare Prompt
            title_str = meeting_title if meeting_title else "General Meeting"
            
            # Prepare User Notes Section
            notes_section = ""
            if user_notes and len(user_notes) > 0:
                notes_section = "\n\n📝 **Human Scribe Notes (TIMELINE LOG - CRITICAL):**\n"
                notes_section += "Use these timestamped notes to identify speakers and verify facts.\n"
                for note in user_notes:
                    notes_section += f"- {note}\n"
                notes_section += "\n(End of Human Notes)\n"
            
            if self.current_summary:
                print("Analyzing audio with incremental context...")
                prompt = (
                    "You are a professional meeting scribe. \n"
                    "We are in the middle of a meeting. Here is the meeting minute so far:\n"
                    f"{self.current_summary}\n\n"
                    f"Meeting Title: {title_str}\n\n"
                    f"{notes_section}"
                    "**Task**: Listen to the ATTACHED AUDIO (which is the next part of the meeting) and UPDATE the meeting minute.\n"
                    "**Instructions:**\n"
                    "1. **Merge** new information into the existing structure (Overview, Key Topics, Decisions, Action Items).\n"
                    "2. **Identify Speakers**: Use the provided Human Scribe Notes to correctly label speakers.\n"
                    "3. Language: **Korean** (keep technical terms in English).\n"
                    "4. Output the **entire updated meeting minute** in Markdown."
                )
            else:
                prompt = (
                    "You are a professional meeting scribe. "
                    "Listen to the attached audio and generate a structured meeting minute.\n"
                    f"Meeting Title: {title_str}\n\n"
                    f"{notes_section}"
                    "**Instructions:**\n"
                    "1. **Identify Speakers**: Distinction between speakers is crucial. Use the Human Scribe Notes to assign names if provided.\n"
                    "2. Language: **Korean** (keep technical terms in English).\n"
                    "3. Format: Use Markdown.\n"
                    "4. Structure:\n"
                    "   - **## 1. 회의 개요 (Overview)**: Brief context.\n"
                    "   - **## 2. 주요 논의 (Key Topics)**: Bullet points of discussed items.\n"
                    "   - **## 3. 결정 사항 (Decisions)**: Clear conclusions.\n"
                    "   - **## 4. 향후 계획 (Action Items)**: To-do list.\n"
                    "   - **## 5. 상세 대화록 (Transcript)**: (Optional) If possible, provide a segmented transcript with speaker labels."
                )

            # 3. Generate Content
            # Note: 1.5 Flash is multimodal and can take the file object directly in the contents list
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, audio_file]
            )
            
            # 4. Extract usage
            usage = None
            if hasattr(response, "usage_metadata"):
                usage = {
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                    "estimated_cost_usd": self._calculate_cost(
                        response.usage_metadata.prompt_token_count,
                        response.usage_metadata.candidates_token_count
                    ),
                    "currency": "USD"
                }
            
            # Update current summary with this high quality version
            self.current_summary = response.text

            return {"summary": response.text, "usage": usage}

        except Exception as e:
            print(f"Error in analyze_audio: {e}")
            return {"error": str(e)}
