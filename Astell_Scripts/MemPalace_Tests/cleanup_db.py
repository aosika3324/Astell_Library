import sys
import os

sys.path.insert(0, r'D:\Astell_Library\mempalace-develop')
from mempalace.palace import get_collection

def clean_and_fix_db():
    db_path = r'D:\Astell_Library\mempalace_db'
    print(f"Connecting to ChromaDB at {db_path}...")
    col = get_collection(db_path)
    
    print("Fetching all database records...")
    res = col.get()
    ids = res.get('ids', [])
    metadatas = res.get('metadatas', [])
    
    print(f"Found {len(ids)} total records.")
    
    to_delete = []
    to_update_ids = []
    to_update_metas = []
    
    for id_, meta in zip(ids, metadatas):
        if not meta:
            continue
            
        source_file = meta.get('source_file', '')
        
        # 1. Check if it belongs to wing_Golden_Mods and mark for deletion
        if 'wing_Golden_Mods' in source_file:
            to_delete.append(id_)
            continue
            
        # 2. Fix the wing tags for mislabeled records
        current_wing = meta.get('wing', '')
        if current_wing == 'Astell_Overmind':
            # Extract the real wing name from the source file path
            # Example path: D:\Astell_Library\Library\wing_Official_SDK\...
            if 'wing_Official_SDK' in source_file:
                meta['wing'] = 'wing_Official_SDK'
                to_update_ids.append(id_)
                to_update_metas.append(meta)
            elif 'wing_Golden_Tutorials' in source_file:
                meta['wing'] = 'wing_Golden_Tutorials'
                to_update_ids.append(id_)
                to_update_metas.append(meta)
            elif 'wing_Astell_Architecture' in source_file:
                meta['wing'] = 'wing_Astell_Architecture'
                to_update_ids.append(id_)
                to_update_metas.append(meta)
    
    # Execute Deletions
    if to_delete:
        print(f"Deleting {len(to_delete)} items belonging to wing_Golden_Mods...")
        col.delete(ids=to_delete)
    else:
        print("No items found for wing_Golden_Mods.")
        
    # Execute Updates
    if to_update_ids:
        print(f"Updating {len(to_update_ids)} items with corrected wing tags (Astell_Overmind -> Real Wing Name)...")
        # To avoid passing too many items at once causing SQLite limits, we can update in batches if it's very large, 
        # but 1000-2000 is typically fine for ChromaDB. We'll batch it to be safe.
        batch_size = 500
        for i in range(0, len(to_update_ids), batch_size):
            batch_ids = to_update_ids[i:i+batch_size]
            batch_metas = to_update_metas[i:i+batch_size]
            col.update(ids=batch_ids, metadatas=batch_metas)
            print(f"  -> Updated batch {i//batch_size + 1} ({len(batch_ids)} items)")
    else:
        print("No items needed wing tag fixing.")
        
    print("Database cleanup and tag fix complete!")

if __name__ == "__main__":
    clean_and_fix_db()