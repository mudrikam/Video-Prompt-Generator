from typing import Dict, Any, List, Callable, Optional
from data_manager.database_helper import get_db_helper
from ai_engine.genai_helper import get_genai_helper
from app_utils.threading_helper import run_in_background, get_thread_manager
from app_utils.config_manager import get_config_manager


class PromptGenerator:
    """Main generator untuk mengelola proses generation prompts"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.db = get_db_helper()
        self.genai = get_genai_helper()
        self.thread_manager = get_thread_manager()
        
        # State tracking
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
            worker_id untuk tracking
        """
        if self.is_generating:
            raise RuntimeError("Generation already in progress")
        
        # Reset stats
        self.generation_stats = {
            'total_videos': len(generation_params.get('videos', [])),
            'processed_videos': 0,
            'total_prompts': 0,
            'successful_prompts': 0,
            'failed_videos': 0
        }
        
        # Start background worker
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
        Worker function untuk background generation
        Runs dalam separate thread
        """
        try:
            videos = generation_params.get('videos', [])
            if not videos:
                if completion_callback:
                    completion_callback(False, "No videos to process", self.generation_stats)
                return
            
            # Update video status ke processing
            for video in videos:
                self.db.update_video_status(video['id'], 'processing')
            
            if progress_callback:
                progress_callback(5, "Starting batch generation...")
            
            # Process each video
            for i, video in enumerate(videos):
                if not self.is_generating:  # Check jika dihentikan
                    break
                
                try:
                    self._process_single_video(video, generation_params, 
                                             i, len(videos), progress_callback)
                    
                    self.generation_stats['processed_videos'] += 1
                    
                except Exception as e:
                    print(f"Error processing video {video['filename']}: {e}")
                    self.generation_stats['failed_videos'] += 1
                    
                    # Update video status ke error
                    self.db.update_video_status(video['id'], 'error')
            
            # Final completion
            if self.is_generating:  # Jika tidak dihentikan
                if progress_callback:
                    progress_callback(100, "Generation completed")
                
                # Return hasil melalui signal, jangan panggil callback langsung
                return self.generation_stats
        
        except Exception as e:
            # Raise exception untuk ditangani oleh signal
            raise RuntimeError(f"Generation failed: {str(e)}")
        
        finally:
            self.is_generating = False
            self.current_worker_id = None
    
    def _process_single_video(self, video: Dict[str, Any], 
                            generation_params: Dict[str, Any],
                            video_index: int, total_videos: int,
                            progress_callback: Optional[Callable] = None) -> None:
        """Process single video untuk generate prompts"""
        
        video_id = video['id']
        video_path = video['filepath']
        
        if progress_callback:
            base_progress = (video_index / total_videos) * 90
            progress_callback(int(base_progress), 
                            f"Processing: {video['filename']}")
        
        try:
            # Validate video file
            is_valid, error_msg = self.genai.validate_video_file(video_path)
            if not is_valid:
                raise RuntimeError(f"Invalid video file: {error_msg}")
            
            # Generate prompts
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
            
            # Save prompts ke database
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
            
            # Update video status ke completed
            self.db.update_video_status(video_id, 'completed')
            
        except Exception as e:
            # Log error dan update status
            print(f"Failed to process video {video['filename']}: {e}")
            self.db.update_video_status(video_id, 'error')
            raise
    
    def _get_completion_message(self) -> str:
        """Generate completion message berdasarkan stats"""
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
        """Check apakah generation sedang berjalan"""
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
        
        # Validate videos
        videos = params['videos']
        if not videos or not isinstance(videos, list):
            return False, "No videos provided"
        
        # Validate numeric parameters
        prompts_per_video = params['prompts_per_video']
        if not isinstance(prompts_per_video, int) or prompts_per_video < 1:
            return False, "Invalid prompts_per_video"
        
        complexity = params['complexity_level']
        if not isinstance(complexity, int) or not (1 <= complexity <= 5):
            return False, "Invalid complexity_level (must be 1-5)"
        
        variation = params['variation_level']
        if not isinstance(variation, int) or not (1 <= variation <= 5):
            return False, "Invalid variation_level (must be 1-5)"
        
        # Validate aspect ratio
        aspect_ratio = params['aspect_ratio']
        valid_ratios = self.config.get_available_aspect_ratios()
        if aspect_ratio not in valid_ratios:
            return False, f"Invalid aspect_ratio. Valid options: {valid_ratios}"
        
        # Check API key
        try:
            self.config.get_api_key()
        except ValueError:
            return False, "GenAI API key not configured"
        
        return True, "Parameters valid"
    
    def get_pending_videos_count(self) -> int:
        """Get jumlah video dengan status pending"""
        all_videos = self.db.get_all_videos()
        return len([v for v in all_videos if v['status'] == 'pending'])
    
    def reset_video_status(self, video_ids: List[int], status: str = 'pending') -> None:
        """Reset status multiple videos"""
        for video_id in video_ids:
            self.db.update_video_status(video_id, status)
    
    def cleanup_failed_videos(self) -> int:
        """Reset status video yang error ke pending"""
        all_videos = self.db.get_all_videos()
        error_videos = [v for v in all_videos if v['status'] == 'error']
        
        for video in error_videos:
            self.db.update_video_status(video['id'], 'pending')
        
        return len(error_videos)


# Singleton instance
_prompt_generator: Optional[PromptGenerator] = None


def get_prompt_generator() -> PromptGenerator:
    """Get singleton instance dari PromptGenerator"""
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = PromptGenerator()
    return _prompt_generator