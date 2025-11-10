from google import genai
import os
from typing import Optional, Dict, Any, List, Callable
import time
import tempfile
from pathlib import Path
from app_utils.config_manager import get_config_manager


class GenAIHelper:
    """Helper for integration with Google GenAI API"""

    def __init__(self):
        self.config = get_config_manager()
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize GenAI client"""
        try:
            api_key = self.config.get_api_key()
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Failed to initialize GenAI client: {e}")
            self.client = None

    def test_connection(self) -> bool:
        """Test connection to GenAI API"""
        if not self.client:
            return False

        try:
            model_name = self.config.get_model_name()
            response = self.client.models.generate_content(
                model=model_name,
                contents=["Test connection: Say 'API connection successful'"]
            )

            if response and response.text:
                return True
            else:
                return False

        except Exception as e:
            print(f"GenAI connection test failed: {e}")
            return False

    def upload_video(self, video_path: str, progress_callback: Optional[Callable] = None) -> Optional[Any]:
        """
        Upload video file to GenAI
        Returns uploaded file object or None if failed
        """
        if not self.client:
            raise RuntimeError("GenAI client not initialized")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        try:
            if progress_callback:
                progress_callback(10, "Starting video upload...")

            uploaded_file = self.client.files.upload(file=video_path)

            if progress_callback:
                progress_callback(50, "Video uploaded, processing...")

            while uploaded_file.state.name == "PROCESSING":
                if progress_callback:
                    progress_callback(70, "Processing video...")
                time.sleep(2)
                uploaded_file = self.client.files.get(name=uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                raise RuntimeError("Video processing failed")

            if progress_callback:
                progress_callback(100, "Video ready for processing")

            return uploaded_file

        except Exception as e:
            raise RuntimeError(f"Failed to upload video: {str(e)}")

    def generate_prompts_batch(self, uploaded_file: Any, complexity_level: int,
                              aspect_ratio: str, variation_level: int,
                              prompts_count: int) -> List[str]:
        """
        Generate multiple prompts in 1 request

        Args:
            uploaded_file: File already uploaded to GenAI
            complexity_level: Complexity level (1-5)
            aspect_ratio: Target aspect ratio
            variation_level: Variation level (1-5)
            prompts_count: Number of prompts requested
        """
        if not self.client:
            raise RuntimeError("GenAI client not initialized")

        complexity_levels = self.config.get_complexity_levels()
        complexity_desc = complexity_levels[complexity_level - 1]

        aspect_ratios = self.config.get_aspect_ratios()
        aspect_desc = aspect_ratios.get(aspect_ratio, "Standard format")

        batch_prompt = self._build_batch_prompt(complexity_desc, aspect_ratio, aspect_desc,
                                               variation_level, prompts_count)

        try:
            model_name = self.config.get_model_name()

            response = self.client.models.generate_content(
                model=model_name,
                contents=[uploaded_file, batch_prompt]
            )

            prompts = self._parse_batch_response(response.text, prompts_count)

            return prompts

        except Exception as e:
            raise RuntimeError(f"Failed to generate prompts: {str(e)}")

    def _build_batch_prompt(self, complexity_desc: str, aspect_ratio: str,
                           aspect_desc: str, variation_level: int, prompts_count: int) -> str:
        """Build batch prompt for multiple generation"""

        variation_instructions = self.config.get_variation_instructions()
        variation_instruction = variation_instructions[str(variation_level)]

        prompt = f"""Analyze this video and generate {prompts_count} distinct AI art prompts based on it.

REQUIREMENTS:
- Complexity Level: {complexity_desc}
- Target Aspect Ratio: {aspect_ratio} ({aspect_desc})
- Variation Strategy: {variation_instruction}
- Generate EXACTLY {prompts_count} different prompts
- Each prompt should be unique and creative
- Format as JSON array with "prompts" key

Please provide the response as valid JSON in this format:
{{
    "prompts": [
        "first prompt text here...",
        "second prompt text here...",
        "third prompt text here..."
    ]
}}

Make sure each prompt is detailed, creative, and suitable for AI art generation tools."""

        return prompt

    def _parse_batch_response(self, response_text: str, expected_count: int) -> List[str]:
        """Parse batch response to extract multiple prompts"""
        import json
        import re

        try:
            data = json.loads(response_text)
            if 'prompts' in data and isinstance(data['prompts'], list):
                return data['prompts'][:expected_count]
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{.*?"prompts".*?\[.*?\].*?\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if 'prompts' in data and isinstance(data['prompts'], list):
                    return data['prompts'][:expected_count]
            except json.JSONDecodeError:
                pass

        lines = response_text.strip().split('\n')
        prompts = []
        for line in lines:
            line = line.strip()
            if re.match(r'^\d+\.', line):
                prompt = re.sub(r'^\d+\.\s*', '', line).strip()
                if prompt and prompt.startswith('"') and prompt.endswith('"'):
                    prompt = prompt[1:-1]
                prompts.append(prompt)
                if len(prompts) >= expected_count:
                    break

        if not prompts:
            prompts = [response_text.strip()]

        return prompts[:expected_count]

    def _build_base_prompt(self, complexity_desc: str, aspect_ratio: str,
                          aspect_desc: str, variation_level: int, prompt_index: int) -> str:
        """Build base prompt for generation"""

        variation_instructions = self.config.get_variation_instructions()
        variation_instruction = variation_instructions[str(variation_level)]

        base_prompt = f"""
Analyze this video and create a detailed video prompt for AI video generation.

Requirements:
- Complexity Level: {complexity_desc}
- Target Aspect Ratio: {aspect_ratio} ({aspect_desc})
- Variation Approach: {variation_instruction}
- Prompt Variation: #{prompt_index}

Instructions:
1. First, analyze the video content, including:
   - Main subjects and objects
   - Actions and movements
   - Setting and environment
   - Lighting and mood
   - Camera angles and movements
   - Visual style and aesthetics

2. Create a comprehensive prompt that includes:
   - Detailed description of subjects
   - Specific actions and movements
   - Environment and setting details
   - Camera movement and angles
   - Lighting and mood specifications
   - Visual style and technical aspects
   - Duration and timing if relevant

3. Optimize the prompt for {aspect_ratio} format:
   - Consider composition suitable for {aspect_desc}
   - Adjust framing and camera angles accordingly
   - Mention aspect ratio requirements if necessary

4. Apply variation level {variation_level}/5:
   {variation_instruction}

5. Format the output as a single, coherent video generation prompt that can be used directly with AI video generation tools.

Generate only the final prompt, no additional explanation or analysis.
        """.strip()

        return base_prompt

    def generate_multiple_prompts(self, video_path: str, num_prompts: int,
                                complexity_level: int, aspect_ratio: str,
                                variation_level: int,
                                progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Generate multiple prompts for one video with auto-split batch
        Automatically splits large requests into smaller batches

        Returns list of generated prompts
        """
        if not self.client:
            raise RuntimeError("GenAI client not initialized")

        max_prompts_per_batch = self.config.get("generation.max_prompts_per_batch")

        uploaded_file = None
        all_prompts = []

        try:
            if progress_callback:
                progress_callback(5, f"Uploading video: {os.path.basename(video_path)}")

            uploaded_file = self.upload_video(video_path,
                lambda p, m: progress_callback(5 + (p * 0.2), m) if progress_callback else None)

            num_batches = (num_prompts + max_prompts_per_batch - 1) // max_prompts_per_batch
            prompts_generated = 0

            if progress_callback:
                if num_batches > 1:
                    progress_callback(25, f"Generating {num_prompts} prompts in {num_batches} batches...")
                else:
                    progress_callback(25, f"Generating {num_prompts} prompts...")

            for batch_num in range(num_batches):
                remaining_prompts = num_prompts - prompts_generated
                batch_size = min(max_prompts_per_batch, remaining_prompts)

                batch_start_progress = 25 + (batch_num / num_batches) * 70
                batch_end_progress = 25 + ((batch_num + 1) / num_batches) * 70

                if progress_callback:
                    progress_callback(
                        int(batch_start_progress),
                        f"Batch {batch_num + 1}/{num_batches}: Generating {batch_size} prompts..."
                    )

                try:
                    batch_prompts = self.generate_prompts_batch(
                        uploaded_file,
                        complexity_level,
                        aspect_ratio,
                        variation_level,
                        batch_size
                    )

                    all_prompts.extend(batch_prompts)
                    prompts_generated += len(batch_prompts)

                    if progress_callback:
                        progress_callback(
                            int(batch_end_progress),
                            f"Batch {batch_num + 1}/{num_batches}: Generated {len(batch_prompts)} prompts"
                        )

                except Exception as batch_error:
                    print(f"Warning: Batch {batch_num + 1} failed: {batch_error}")
                    # Continue with next batch instead of failing completely
                    if progress_callback:
                        progress_callback(
                            int(batch_end_progress),
                            f"Batch {batch_num + 1}/{num_batches}: Failed, continuing..."
                        )

            if progress_callback:
                progress_callback(100, f"Generated {len(all_prompts)} prompts successfully")

            return all_prompts[:num_prompts]

        except Exception as e:
            print(f"Error in generate_multiple_prompts: {str(e)}")
            raise RuntimeError(f"Failed to generate prompts: {str(e)}")

        finally:
            if uploaded_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except Exception as cleanup_error:
                    print(f"Failed to cleanup uploaded file: {cleanup_error}")

    def batch_generate_prompts(self, videos: List[Dict[str, Any]],
                             generation_params: Dict[str, Any],
                             progress_callback: Optional[Callable] = None) -> Dict[int, List[str]]:
        """
        Batch generate prompts for multiple videos

        Args:
            videos: List of video dictionaries from database
            generation_params: Dict with generation parameters
            progress_callback: Progress callback function

        Returns:
            Dict mapping video_id to list of generated prompts
        """
        results = {}
        total_videos = len(videos)

        for i, video in enumerate(videos):
            try:
                if progress_callback:
                    overall_progress = (i / total_videos) * 100
                    progress_callback(int(overall_progress),
                                    f"Processing video {i+1}/{total_videos}: {video['filename']}")

                prompts = self.generate_multiple_prompts(
                    video['filepath'],
                    generation_params['prompts_per_video'],
                    generation_params['complexity_level'],
                    generation_params['aspect_ratio'],
                    generation_params['variation_level'],
                    lambda p, m: progress_callback(
                        int(overall_progress + (p / total_videos)), m
                    ) if progress_callback else None
                )

                results[video['id']] = prompts

            except Exception as e:
                print(f"Failed to process video {video['filename']}: {e}")
                results[video['id']] = []

        if progress_callback:
            progress_callback(100, "Batch generation completed")

        return results

    def update_api_key(self, new_api_key: str) -> bool:
        """Update API key and reinitialize client"""
        try:
            self.config.set_api_key(new_api_key)
            self._initialize_client()
            return self.test_connection()
        except Exception:
            return False

    def get_supported_formats(self) -> List[str]:
        """Get list of video formats supported by GenAI"""
        return self.config.get_supported_video_formats()

    def validate_video_file(self, video_path: str) -> tuple[bool, str]:
        """
        Validate video file for GenAI processing

        Returns:
            (is_valid, error_message)
        """
        if not os.path.exists(video_path):
            return False, "File does not exist"

        _, ext = os.path.splitext(video_path.lower())
        if ext not in self.get_supported_formats():
            return False, f"Unsupported format: {ext}"

        file_size = os.path.getsize(video_path)
        max_size = self.config.get_max_file_size_mb() * 1024 * 1024
        if file_size > max_size:
            return False, f"File too large: {file_size / (1024*1024):.1f}MB"

        try:
            with open(video_path, 'rb') as f:
                f.read(1024)
        except Exception:
            return False, "File is not readable"

        return True, "Valid video file"


# Singleton instance
_genai_helper: Optional[GenAIHelper] = None


def get_genai_helper() -> GenAIHelper:
    """Get singleton instance of GenAIHelper"""
    global _genai_helper
    if _genai_helper is None:
        _genai_helper = GenAIHelper()
    return _genai_helper