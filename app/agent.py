# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import urllib.parse
import urllib.request
import uuid
from google.cloud import firestore, storage
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import Client, types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback

# HARDCODED GCP Project ID and Storage Bucket Name
GCP_PROJECT_ID = "qwiklabs-gcp-03-ef01b95861de"
GCS_BUCKET_NAME = "cinematic-storyboards-qwiklabs-gcp-03-ef01b95861de"
COLLECTION_NAME = "storyboard_shots"
MEMORY_BANK_ID = "3386911428945379328"

# Read Agent Engine resource name from deployment_metadata.json if available
DEPLOYMENT_METADATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "deployment_metadata.json"
)
AGENT_ENGINE_RESOURCE_NAME = None
if os.path.exists(DEPLOYMENT_METADATA_PATH):
    try:
        with open(DEPLOYMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
            AGENT_ENGINE_RESOURCE_NAME = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Failed to load deployment_metadata.json: {e}")


# Initialize AgentEngineSandboxCodeExecutor for secure Agent Platform sandbox code execution
code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME
)


# Memory Bank Service builder for deployment
def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=GCP_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


memory_service = memory_bank_service_builder()


# Callback to write session turns to Memory Bank for extraction
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory callback skipped: {e}")
    return None


def get_firestore_db() -> firestore.Client:
    """Returns a Firestore client instance configured with the hardcoded project ID."""
    return firestore.Client(project=GCP_PROJECT_ID)


def list_storyboard_shots(filter_style: str = "") -> str:
    """List or search storyboard shots stored in the Firestore database.

    Args:
        filter_style: Optional director style (e.g. 'Denis Villeneuve', 'Wes Anderson') to filter by.

    Returns:
        JSON string representing the list of storyboard shots.
    """
    db = get_firestore_db()
    docs = db.collection(COLLECTION_NAME).stream()
    shots = []
    for doc in docs:
        data = doc.to_dict()
        if filter_style:
            if filter_style.lower() in data.get("director_style", "").lower():
                shots.append(data)
        else:
            shots.append(data)

    if not shots:
        return f"No storyboard shots found{' matching filter ' + filter_style if filter_style else ''}."

    return json.dumps(shots, indent=2)


def get_storyboard_shot(shot_id: str) -> str:
    """Retrieve details for a specific storyboard shot by its ID.

    Args:
        shot_id: The unique identifier of the shot (e.g., 'shot_001').

    Returns:
        JSON string of the shot details or an error message if not found.
    """
    db = get_firestore_db()
    doc_ref = db.collection(COLLECTION_NAME).document(shot_id)
    doc = doc_ref.get()

    if not doc.exists:
        return f"Shot with ID '{shot_id}' not found."

    return json.dumps(doc.to_dict(), indent=2)


def save_storyboard_shot(
    shot_id: str,
    title: str,
    scene_number: int,
    shot_type: str,
    description: str,
    lighting_setup: str,
    lens_mm: str,
    director_style: str,
) -> str:
    """Save or update a storyboard shot in the Firestore database.

    Args:
        shot_id: Unique identifier for the shot (e.g. 'shot_004').
        title: Short descriptive title of the shot.
        scene_number: Scene sequence number.
        shot_type: Framing style (e.g., 'Extreme Wide Shot', 'Close-up', 'Dolly Zoom').
        description: Visual action and composition description.
        lighting_setup: Lighting direction and color mood.
        lens_mm: Lens focal length (e.g., '35mm Anamorphic', '50mm F1.2').
        director_style: Aesthetic director influence (e.g., 'Christopher Nolan').

    Returns:
        Confirmation message upon successful write.
    """
    db = get_firestore_db()
    shot_data = {
        "shot_id": shot_id,
        "title": title,
        "scene_number": scene_number,
        "shot_type": shot_type,
        "description": description,
        "lighting_setup": lighting_setup,
        "lens_mm": lens_mm,
        "director_style": director_style,
    }
    db.collection(COLLECTION_NAME).document(shot_data["shot_id"]).set(shot_data)
    return f"Successfully saved storyboard shot '{shot_id}' ({title}) to Firestore."


def calculate_depth_of_field(
    focal_length_mm: float,
    aperture_f_stop: float,
    subject_distance_feet: float,
    sensor_format: str = "full_frame",
) -> str:
    """Calculate the Depth of Field (DoF), hyperfocal distance, and near/far focus limits for a camera lens setup.

    Args:
        focal_length_mm: Lens focal length in millimeters (e.g. 50.0).
        aperture_f_stop: Lens aperture f-number (e.g. 1.8, 2.8, 5.6).
        subject_distance_feet: Distance to subject in feet (e.g. 10.0).
        sensor_format: Camera sensor format ('full_frame', 'super35', or 'apsc'). Default is 'full_frame'.

    Returns:
        JSON string containing hyperfocal_distance_feet, near_limit, far_limit, and total_depth_of_field.
    """
    coc_mm = 0.029 if "super" not in sensor_format.lower() and "apsc" not in sensor_format.lower() else 0.019
    h_feet = (focal_length_mm ** 2) / (aperture_f_stop * coc_mm * 304.8)

    d = subject_distance_feet
    f_feet = focal_length_mm / 304.8

    near_limit = (h_feet * d) / (h_feet + (d - f_feet))

    if d >= h_feet:
        far_limit_str = "Infinity"
        total_dof_str = "Infinity"
    else:
        far_limit = (h_feet * d) / (h_feet - (d - f_feet))
        far_limit_str = f"{far_limit:.2f} ft"
        total_dof_str = f"{far_limit - near_limit:.2f} ft"

    res = {
        "focal_length_mm": focal_length_mm,
        "aperture_f_stop": aperture_f_stop,
        "subject_distance_feet": subject_distance_feet,
        "sensor_format": sensor_format,
        "hyperfocal_distance_feet": f"{h_feet:.2f} ft",
        "near_limit": f"{near_limit:.2f} ft",
        "far_limit": far_limit_str,
        "total_depth_of_field": total_dof_str,
    }
    return json.dumps(res, indent=2)


def search_cinematic_references(query: str) -> str:
    """Search public movie and TV show databases for cinematic titles, genres, summaries, ratings, and poster references.

    Args:
        query: Movie or show title to search for (e.g., 'Dune', 'Blade Runner', 'Succession').

    Returns:
        JSON string containing matching titles, premiered date, genres, rating, summary, and poster image URL.
    """
    api_key = os.getenv("CINEMA_API_KEY") or os.getenv("TVMAZE_API_KEY")

    encoded_query = urllib.parse.quote(query)
    url = f"https://api.tvmaze.com/search/shows?q={encoded_query}"
    if api_key:
        url += f"&apikey={api_key}"

    req = urllib.request.Request(url, headers={"User-Agent": "CinematicDirectorAgent/1.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data[:3]:
                show = item.get("show", {})
                summary_raw = show.get("summary") or ""
                summary_clean = (
                    summary_raw.replace("<p>", "")
                    .replace("</p>", "")
                    .replace("<b>", "")
                    .replace("</b>", "")
                    .replace("<i>", "")
                    .replace("</i>", "")
                    .strip()
                )
                results.append({
                    "title": show.get("name"),
                    "premiered": show.get("premiered"),
                    "genres": show.get("genres", []),
                    "rating": show.get("rating", {}).get("average"),
                    "network": show.get("network", {}).get("name") if show.get("network") else "Streaming",
                    "summary": summary_clean,
                    "poster_image_url": show.get("image", {}).get("medium") if show.get("image") else None,
                })
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error fetching cinematic references: {str(e)}"


def generate_storyboard_image(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a visual 16:9 cinematic storyboard image frame using the gemini-3.1-flash-lite-image model, save it as a Playground artifact, and upload it to Cloud Storage.

    Args:
        prompt: Detailed visual prompt describing the storyboard shot composition, lighting, and action.
        tool_context: Context object passed automatically by the framework for saving artifacts.

    Returns:
        Public HTTPS URL string pointing to the uploaded image in Cloud Storage.
    """
    genai_client = Client(vertexai=True, project=GCP_PROJECT_ID, location="global")
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=f"Cinematic 16:9 film storyboard concept frame: {prompt}",
    )

    part = response.candidates[0].content.parts[0]
    image_bytes = part.inline_data.data
    mime_type = part.inline_data.mime_type or "image/jpeg"

    unique_id = uuid.uuid4().hex[:8]
    filename = f"storyboard_{unique_id}.jpg"

    # 1. Save artifact for Playground Artifacts panel
    tool_context.save_artifact(
        filename=filename,
        artifact=types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
    )

    # 2. Upload image bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return f"Generated storyboard image successfully! Public Cloud Storage URL: {public_url}"


def generate_cinematic_video(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a short 16:9 cinematic video storyboard preview using the gemini-omni-flash-preview model in the global region, save it as a Playground artifact, and upload it to Cloud Storage.

    Args:
        prompt: Detailed visual description of the cinematic video shot composition, camera motion, lighting, and action.
        tool_context: Context object passed automatically by the framework for saving artifacts.

    Returns:
        Public HTTPS URL string pointing to the uploaded video in Cloud Storage.
    """
    genai_client = Client(vertexai=True, project=GCP_PROJECT_ID, location="global")
    response = genai_client.models.generate_content(
        model="gemini-omni-flash-preview",
        contents=f"Cinematic 16:9 animated video shot preview: {prompt}",
    )

    part = response.candidates[0].content.parts[0]
    video_bytes = part.inline_data.data
    mime_type = part.inline_data.mime_type or "video/mp4"

    unique_id = uuid.uuid4().hex[:8]
    filename = f"cinematic_video_{unique_id}.mp4"

    # 1. Save artifact for Playground Artifacts panel
    tool_context.save_artifact(
        filename=filename,
        artifact=types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
    )

    # 2. Upload video bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return f"Generated cinematic video successfully! Public Cloud Storage URL: {public_url}"


# Build A2UI System Prompt (v0.8 with BasicCatalog)
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_prompt = schema_manager.generate_system_prompt(
    role_description=(
        "An expert Cinematic Movie Director and Storyboard Creator agent. You help filmmakers plan scenes, "
        "calculate optical Depth of Field (DoF), search for cinematic references (film/show metadata), "
        "generate visual 16:9 storyboard frames and animated video clips, execute Python calculations safely in a sandbox environment, "
        "manage shot lists, and curate storyboard shots in Firestore."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

memory_instructions = (
    "\n\nMEMORY INSTRUCTIONS: You have an active Memory Bank. Ensure you record and retain all user preferences "
    "according to our project requirements across sessions: "
    "1. Screenplay plot notes and storyline details. "
    "2. Preferred visual director styles (e.g., Denis Villeneuve, Wes Anderson, Christopher Nolan, Ridley Scott). "
    "3. Past shot list decisions, composition choices, and framing styles. "
    "4. Project camera rig settings (lens focal lengths, aspect ratios, lighting setups, sensor formats). "
    "Whenever the user shares or updates any of these preferences, acknowledge them explicitly and apply "
    "them across all future shot list, Depth of Field, and storyboard image generation requests."
)

agent_instruction = a2ui_prompt + memory_instructions


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=agent_instruction,
    tools=[
        PreloadMemoryTool(),
        list_storyboard_shots,
        get_storyboard_shot,
        save_storyboard_shot,
        calculate_depth_of_field,
        search_cinematic_references,
        generate_storyboard_image,
        generate_cinematic_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
