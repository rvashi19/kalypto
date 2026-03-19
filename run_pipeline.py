import os
import sys
import argparse
import warnings
from dotenv import load_dotenv

def main():
    # Ignore future warnings from libraries like librosa
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    # Load environment variables
    env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()

    parser = argparse.ArgumentParser(
        description="Emotion-Preserving AI Video Dubbing -- Modular Backbone"
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="Path to input video or audio file"
    )
    parser.add_argument(
        "--target-lang", type=str, default="Spanish",
        help="Target language for dubbing (default: Spanish)"
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = args.input

    # Default fallbacks: Warn and require real speech if no input provided
    if not input_path:
        if os.path.exists(os.path.join(script_dir, "speech_sample.wav")):
            input_path = os.path.join(script_dir, "speech_sample.wav")
            print("[INFO] Defaulting to SYNTHETIC BASELINE speech sample (speech_sample.wav).")
            print("       NOTE: Provide a real human mp4 via --input for scientifically valid outputs.")
        else:
            print("\n" + "!"*70)
            print(" [WARNING] No --input provided. Defaulting to pre-packaged dummy samples.")
            print("           The default sample is classified as NON-SPEECH / INVALID.")
            print("           All prosody, emotion, and alignment metrics will be NULL/WEAK.")
            print("           To see real results, please provide a REAL SPOKEN AUDIO FILE:")
            print("           Example: python run_pipeline.py --input my_speech.wav")
            print("!"*70 + "\n")
            if os.path.exists(os.path.join(script_dir, "audio.aac")):
                input_path = os.path.join(script_dir, "audio.aac")
            elif os.path.exists(os.path.join(script_dir, "video.mp4")):
                input_path = os.path.join(script_dir, "video.mp4")
            else:
                print("[ERROR] No fallback files found. Provide one via --input")
                sys.exit(1)

    if not os.path.exists(input_path):
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    # Delegate immediately to the Orchestrator
    try:
        from backend.pipeline.orchestrator import DubbingOrchestrator
    except ImportError as e:
        print(f"[ERROR] Could not import backend.pipeline modules. Ensure you're running from project root. ({e})")
        sys.exit(1)

    results_dir = os.path.join(script_dir, "results")
    orchestrator = DubbingOrchestrator(
        input_path=input_path,
        target_lang=args.target_lang,
        output_dir=results_dir
    )
    
    # Run the modular pipeline
    orchestrator.run()

if __name__ == "__main__":
    main()
