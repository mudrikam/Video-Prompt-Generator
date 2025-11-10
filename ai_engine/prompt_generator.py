from typing import Dict, Any, List, Callable, Optional
from data_manager.database_helper import get_db_helper
from ai_engine.genai_helper import get_genai_helper
from app_utils.threading_helper import run_in_background, get_thread_manager
from app_utils.config_manager import get_config_manager


class PromptGenerator:
    """Main generator for managing prompt generation process"""

    def __init__(self):
        self.config = get_config_manager()
        self.db = get_db_helper()
        self.genai = get_genai_helper()
        self.thread_manager = get_thread_manager()

        self.is_generating = False
        self.current_worker_id = None
        self.generation_stats = {
            'total_videos': 0,
            'processed_videos': 0,
            'total_prompts': 0,
            'successful_prompts': 0,
            'failed_videos': 0
        }

    def start_generation(self, generation_params: Dict[str, Any],
                        progress_callback: Optional[Callable] = None,
                        completion_callback: Optional[Callable] = None) -> str:
        """
        Start batch generation process

        Args:
            generation_params: Dict containing generation parameters
            progress_callback: Function(percentage, message)
            completion_callback: Function(success, message, stats)

        Returns:
            worker_id for tracking
        """
        if self.is_generating:
            raise RuntimeError("Generation already in progress")

        self.generation_stats = {
            'total_videos': len(generation_params.get('videos', [])),
            'processed_videos': 0,
            'total_prompts': 0,
            'successful_prompts': 0,
            'failed_videos': 0
        }

        self.current_worker_id = run_in_background(
            self._generation_worker,
            generation_params,
            progress_callback=progress_callback,
            completion_callback=completion_callback
        )

        self.is_generating = True
        return self.current_worker_id

    def stop_generation(self) -> bool:
        """Stop current generation process"""
        if not self.is_generating or not self.current_worker_id:
            return False

        success = self.thread_manager.stop_worker(self.current_worker_id)
        if success:
            self.is_generating = False
            self.current_worker_id = None

        return success

    def _generation_worker(self, generation_params: Dict[str, Any],
                          progress_callback: Optional[Callable] = None,
                          completion_callback: Optional[Callable] = None,
                          **kwargs) -> None:
        """
        Worker function for background generation
        Runs in separate thread
        """
        try:
            videos = generation_params.get('videos', [])
            if not videos:
                if completion_callback:
                    completion_callback(False, "No videos to process", self.generation_stats)
                return

            for video in videos:
                self.db.update_video_status(video['id'], 'processing')

            if progress_callback:
                progress_callback(5, "Starting batch generation...")

            for i, video in enumerate(videos):
                if not self.is_generating:
                    break

                try:
                    self._process_single_video(video, generation_params,
                                             i, len(videos), progress_callback)

                    self.generation_stats['processed_videos'] += 1

                except Exception as e:
                    print(f"Error processing video {video['filename']}: {e}")
                    self.generation_stats['failed_videos'] += 1

                    self.db.update_video_status(video['id'], 'error')

            if self.is_generating:
                if progress_callback:
                    progress_callback(100, "Generation completed")

                return self.generation_stats

        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

        finally:
            self.is_generating = False
            self.current_worker_id = None

    def _process_single_video(self, video: Dict[str, Any],
                            generation_params: Dict[str, Any],
                            video_index: int, total_videos: int,
                            progress_callback: Optional[Callable] = None) -> None:
        """Process single video to generate prompts"""

        video_id = video['id']
        video_path = video['filepath']

        if progress_callback:
            base_progress = (video_index / total_videos) * 90
            progress_callback(int(base_progress),
                            f"Processing: {video['filename']}")

        try:
            is_valid, error_msg = self.genai.validate_video_file(video_path)
            if not is_valid:
                raise RuntimeError(f"Invalid video file: {error_msg}")

            prompts = self.genai.generate_multiple_prompts(
                video_path,
                generation_params['prompts_per_video'],
                generation_params['complexity_level'],
                generation_params['aspect_ratio'],
                generation_params['variation_level'],
                lambda p, m: progress_callback(
                    int(base_progress + (p / total_videos)), m
                ) if progress_callback else None
            )

            successful_prompts = 0
            for prompt_text in prompts:
                if prompt_text and prompt_text.strip():
                    self.db.add_prompt(
                        video_id,
                        prompt_text.strip(),
                        generation_params['complexity_level'],
                        generation_params['aspect_ratio'],
                        generation_params['variation_level']
                    )
                    successful_prompts += 1

            self.generation_stats['total_prompts'] += len(prompts)
            self.generation_stats['successful_prompts'] += successful_prompts

            self.db.update_video_status(video_id, 'completed')

        except Exception as e:
            print(f"Failed to process video {video['filename']}: {e}")
            self.db.update_video_status(video_id, 'error')
            raise

    def _get_completion_message(self) -> str:
        """Generate completion message based on stats"""
        stats = self.generation_stats

        if stats['failed_videos'] == 0:
            return (f"Successfully generated {stats['successful_prompts']} prompts "
                   f"from {stats['processed_videos']} videos")
        else:
            return (f"Generated {stats['successful_prompts']} prompts from "
                   f"{stats['processed_videos']} videos. {stats['failed_videos']} videos failed.")

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get current generation statistics"""
        return self.generation_stats.copy()

    def is_generation_active(self) -> bool:
        """Check if generation is currently running"""
        return self.is_generating

    def validate_generation_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate generation parameters

        Returns:
            (is_valid, error_message)
        """
        required_keys = ['videos', 'prompts_per_video', 'complexity_level',
                        'aspect_ratio', 'variation_level']

        for key in required_keys:
            if key not in params:
                return False, f"Missing parameter: {key}"

        videos = params['videos']
        if not videos or not isinstance(videos, list):
            return False, "No videos provided"

        prompts_per_video = params['prompts_per_video']
        if not isinstance(prompts_per_video, int) or prompts_per_video < 1:
            return False, "Invalid prompts_per_video"

        complexity = params['complexity_level']
        min_complexity, max_complexity = self.config.get_complexity_range()
        if not isinstance(complexity, int) or not (min_complexity <= complexity <= max_complexity):
            return False, f"Invalid complexity_level (must be {min_complexity}-{max_complexity})"

        variation = params['variation_level']
        min_variation, max_variation = self.config.get_variation_range()
        if not isinstance(variation, int) or not (min_variation <= variation <= max_variation):
            return False, f"Invalid variation_level (must be {min_variation}-{max_variation})"

        aspect_ratio = params['aspect_ratio']
        valid_ratios = self.config.get_available_aspect_ratios()
        if aspect_ratio not in valid_ratios:
            return False, f"Invalid aspect_ratio. Valid options: {valid_ratios}"

        try:
            self.config.get_api_key()
        except ValueError:
            return False, "GenAI API key not configured"

        return True, "Parameters valid"

    def get_pending_videos_count(self) -> int:
        """Get count of videos with pending status"""
        all_videos = self.db.get_all_videos()
        return len([v for v in all_videos if v['status'] == 'pending'])

    def reset_video_status(self, video_ids: List[int], status: str = 'pending') -> None:
        """Reset status of multiple videos"""
        for video_id in video_ids:
            self.db.update_video_status(video_id, status)

    def cleanup_failed_videos(self) -> int:
        """Reset status of error videos to pending"""
        all_videos = self.db.get_all_videos()
        error_videos = [v for v in all_videos if v['status'] == 'error']

        for video in error_videos:
            self.db.update_video_status(video['id'], 'pending')

        return len(error_videos)


# Singleton instance
_prompt_generator: Optional[PromptGenerator] = None


def get_prompt_generator() -> PromptGenerator:
    """Get singleton instance of PromptGenerator"""
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = PromptGenerator()
    return _prompt_generator