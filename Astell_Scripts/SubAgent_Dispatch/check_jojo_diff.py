import os
import glob
import re

def extract_identifiers_from_file(filepath):
    identifiers = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract JSON identifiers: masonliu:xxx or travel:xxx
            matches = re.findall(r'(?:masonliu|travel|jojo):[a-zA-Z0-9_]+', content)
            identifiers.update(matches)
            
            # Extract event names
            events = re.findall(r'ListenForEvent\([^,]+,\s*[^,]+,\s*["\']([^"\']+)["\']', content)
            identifiers.update(events)
            
            # Extract Python classes
            classes = re.findall(r'class\s+([a-zA-Z0-9_]+)', content)
            identifiers.update(classes)
    except Exception as e:
        pass
    return identifiers

def main():
    print("🔍 [Astell Skeptic] Starting Full Diff Verification...")
    
    source_dir = "Explore/jojo"
    capsule_dir = "Library/wing_Golden_Mods"
    
    source_files = glob.glob(f"{source_dir}/**/*.*", recursive=True)
    capsule_files = glob.glob(f"{capsule_dir}/**/*.*", recursive=True)
    
    source_ids = set()
    capsule_ids = set()
    
    print(f"Scanning {len(source_files)} source files...")
    for f in source_files:
        if f.endswith('.json') or f.endswith('.py') or f.endswith('.md'):
            source_ids.update(extract_identifiers_from_file(f))
            
    print(f"Scanning {len(capsule_files)} capsule files...")
    for f in capsule_files:
        if f.endswith('.json') or f.endswith('.py') or f.endswith('.md'):
            capsule_ids.update(extract_identifiers_from_file(f))
            
    # Remove some common generic bedrock events to reduce noise
    noise = {'ClientPlayerAddEvent', 'ServerPlayerAddEvent', 'ClientEntityTickEvent', 'ServerEntityTickEvent'}
    source_ids = source_ids - noise
    capsule_ids = capsule_ids - noise
    
    missing = source_ids - capsule_ids
    
    print("\n" + "="*50)
    print(f"✅ Source Identifiers Found: {len(source_ids)}")
    print(f"✅ Capsule Identifiers Captured: {len(capsule_ids)}")
    print(f"⚠️  Missing Identifiers (Omissions): {len(missing)}")
    print("="*50)
    
    if len(missing) > 0:
        print("\n[WARNING] The following mechanics/identifiers were completely missed by the sub-agents:")
        for m in sorted(list(missing))[:30]: # Show top 30
            print(f"  - {m}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more.")
        print("\n=> Action Required: Dispatch Skeptic to patch these missing identifiers into the appropriate capsules.")
    else:
        print("\n[SUCCESS] 100% Coverage achieved. No omissions detected!")

if __name__ == "__main__":
    main()