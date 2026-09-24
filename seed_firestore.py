"""Seed script to populate Firestore database for Cinematic Movie Director & Storyboard Creator."""

from google.cloud import firestore

# HARDCODED GCP Project ID (Do NOT use GOOGLE_CLOUD_PROJECT or auth defaults)
GCP_PROJECT_ID = "qwiklabs-gcp-03-ef01b95861de"

COLLECTION_NAME = "storyboard_shots"

SAMPLE_SHOTS = [
    {
        "shot_id": "shot_001",
        "title": "Desert Horizon Sunrise",
        "scene_number": 1,
        "shot_type": "Extreme Wide Shot",
        "description": "A solitary traveler walks across vast golden sand dunes as dual suns rise on the horizon.",
        "lighting_setup": "Warm backlight, golden hour natural rim light",
        "lens_mm": "24mm Anamorphic",
        "director_style": "Denis Villeneuve",
    },
    {
        "shot_id": "shot_002",
        "title": "Symmetrical Observatory Corridor",
        "scene_number": 2,
        "shot_type": "Medium Full Shot",
        "description": "Perfectly centered view of a pastel-pink control room with vintage analog instruments.",
        "lighting_setup": "Soft diffused overhead lighting, pastel pastel palette",
        "lens_mm": "35mm Prime",
        "director_style": "Wes Anderson",
    },
    {
        "shot_id": "shot_003",
        "title": "Rainy Cyberpunk Alley Pursuit",
        "scene_number": 3,
        "shot_type": "Dolly Zoom (Vertigo Effect)",
        "description": "Neon-lit alleyway reflection in puddles as a detective turns back towards a shadowed pursuer.",
        "lighting_setup": "High contrast neon blue & magenta specular highlights",
        "lens_mm": "50mm F1.2",
        "director_style": "Ridley Scott",
    },
]


def seed_database():
    db = firestore.Client(project=GCP_PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    print(f"Seeding '{COLLECTION_NAME}' into Firestore (project: {GCP_PROJECT_ID})...")
    for shot in SAMPLE_SHOTS:
        doc_ref = collection_ref.document(shot["shot_id"])
        doc_ref.set(shot)
        print(f"  ✓ Added document: {shot['shot_id']} - {shot['title']}")

    print("Seeding complete!")


if __name__ == "__main__":
    seed_database()
