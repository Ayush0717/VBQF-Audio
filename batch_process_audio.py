import glob
import logging
import traceback
from pathlib import Path
import time

from app import process_audio
from config import DEFAULT_CONFIG
from utils.logging import configure_logging

def main():
    configure_logging(False) # Set True for debug logs
    
    # Find all wav files in data/audio
    audio_dir = Path("data/audio")
    audio_files = list(audio_dir.glob("*.wav"))
    
    if not audio_files:
        print(f"No .wav files found in {audio_dir.absolute()}")
        return
        
    print(f"Found {len(audio_files)} audio files to process.")
    
    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    for audio_path in audio_files:
        output_path = output_dir / f"{audio_path.stem}_features.json"
        
        print(f"\n[{success_count + fail_count + 1}/{len(audio_files)}] Processing {audio_path.name}...")
        start_time = time.time()
        
        try:
            process_audio(audio_path, output_path=output_path, config=DEFAULT_CONFIG)
            elapsed = time.time() - start_time
            print(f"✅ Success! Saved to {output_path.name} (took {elapsed:.1f}s)")
            success_count += 1
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Failed to process {audio_path.name} (took {elapsed:.1f}s)")
            print(f"Error: {e}")
            traceback.print_exc()
            fail_count += 1
            
    print("\n" + "="*50)
    print("Batch Processing Complete!")
    print(f"Successfully processed: {success_count}")
    print(f"Failed to process:      {fail_count}")
    print("="*50)
    
    try:
        from analytics.batch_csv_export import generate_batch_csv
        print("\nGenerating batch CSV report...")
        out_csv = generate_batch_csv()
        print(f"✅ Master CSV created: {out_csv}")
    except Exception as e:
        print(f"❌ Failed to generate master CSV: {e}")
        traceback.print_exc()

if __name__ == "__main__":

    main()
