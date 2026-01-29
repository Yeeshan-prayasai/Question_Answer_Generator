import os
import sys
import streamlit as st
import asyncio
import pandas as pd
import uuid
import json
import time
import warnings
import random
from io import BytesIO
from dotenv import load_dotenv
from collections import Counter

# Suppress async cleanup warnings in Python 3.13+
warnings.filterwarnings('ignore', message='Event loop is closed')

# Ensure the project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Load environment variables
load_dotenv()

# UPSC Prelims Syllabus for Subject/Topic Picker
syllabus = {
    "History": [
        "Ancient History",
        "Modern History",
        "Post-Independence",
        "Art & Culture",
        "Medieval History"
    ],
    "Geography": [
        "Mapping",
        "World Geography",
        "Human Geography",
        "Physical Geography",
        "Indian Geography"
    ],
    "Polity": [
        "Electoral Process",
        "State Government",
        "Governance",
        "Local Governance",
        "Statutory Bodies",
        "Union Government",
        "Constitutional Bodies",
        "Constitution"
    ],
    "Economy": [
        "Banking & Finance",
        "External Sector",
        "Budget & Finance",
        "Economic Sectors",
        "Dev. Indicators",
        "Inclusive Growth",
        "Macroeconomics"
    ],
    "Environment": [
        "Ecology",
        "Environmental Law",
        "Biodiversity",
        "Int. Conventions",
        "Protected Areas",
        "Climate Change",
        "Pollution",
        "Env. Management"
    ],
    "Science & Tech": [
        "Space Science",
        "Defence Tech",
        "Biotechnology",
        "ICT",
        "Energy Tech",
        "Basic Science",
        "Disaster Mgmt."
    ],
    "Current Affairs": [
        "Economy",
        "Polity & Governance",
        "Other Current Affairs",
        "International Relations",
        "Social Issues",
        "Science & Technology",
        "Environment"
    ],
    "Miscellaneous": [
        "Reports & Indices",
        "Personalities",
        "Awards",
        "Places in News",
        "Defence Exercises",
        "Culture",
        "Sports"
    ]
}

# Import from module
try:
    from module.manager import QuestionManager
    from module.exporter import generate_upsc_docx
    from module.models import Question
except ImportError:
    from manager import QuestionManager
    from exporter import generate_upsc_docx
    from models import Question

# --- API Key Setup ---
# api_key = st.secrets["api_key"]
api_key = os.getenv("api_key")
if not api_key:
    env_path = os.path.join(root_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        api_key = st.secrets["api_key"]

if not api_key:
    st.error("GEMINI_API_KEY (api_key) not found.")
    st.stop()

# --- Initialize Manager ---
if 'manager' not in st.session_state:
    try:
        st.session_state.manager = QuestionManager(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Manager: {e}")
        st.stop()

manager = st.session_state.manager

# --- HEARTBEAT / KEEP-ALIVE ---
@st.fragment(run_every=120)  # Reruns every 2 minutes (120 seconds)
def keep_alive_heartbeat():
    """
    Silent fragment that sends a 'ping' to the server every 2 minutes.
    This prevents the WebSocket connection from timing out while 
    experts are reading or researching a question.
    """
    pass

# --- Page Config ---
st.set_page_config(
    page_title="PrayasAI UPSC Generator",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

def parse_blueprint_config(df_bp):
    """Parses blueprint inputs for question generation from structured DataFrame."""
    config_list = []
    
    # Check if new format (Topic, Pattern, Cognitive, Difficulty, Count)
    required_cols = ['Pattern', 'Cognitive', 'Difficulty', 'Count']
    if all(col in df_bp.columns for col in required_cols):
        for _, row in df_bp.iterrows():
            try:
                cnt = int(row['Count'])
                if cnt > 0:
                    config_list.append({
                        "topic": str(row.get('Topic', '') if pd.notna(row.get('Topic')) else '').strip(),
                        "pattern": row['Pattern'],
                        "cognitive": row['Cognitive'],
                        "difficulty": row['Difficulty'],
                        "count": cnt
                    })
            except Exception as e:
                print(f"Skipping row due to error: {e}")
                continue
    else:
        st.error("Uploaded Blueprint does not match required columns: Topic, Pattern, Cognitive, Difficulty, Count")
        
    return config_list

# Load default blueprint
try:
    default_bp_df = pd.read_excel('./prompts/default_blueprint.xlsx')
    default_config = parse_blueprint_config(default_bp_df)
except Exception:
    default_config = []


# --- Styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .stButton>button {
        font-weight: 600;
    }
    .question-block {
        margin-bottom: 1.5rem;
        padding: 1rem;
        border: 1px solid #ddd;
        border-radius: 8px;
        background-color: #f9f9f9;
    }
    .status-badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .status-selected { background-color: #d4edda; color: #155724; }
    .status-rejected { background-color: #f8d7da; color: #721c24; }
    .unsaved-warning {
        padding: 1rem;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Callbacks ---
def move_question(list_key, index, direction):
    """Callback to move question up (-1) or down (+1)"""
    qs = st.session_state.get(list_key)
    if not qs: return
    
    new_index = index + direction
    if 0 <= new_index < len(qs):
        qs[index], qs[new_index] = qs[new_index], qs[index]
        # We don't update question_number here, we do it on save or display?
        # Better to update numbering logic in render or save.
        st.session_state[list_key] = qs

def update_selection(list_key, index, action, key_prefix):
    """Callback for mutual exclusion of Select/Reject"""
    qs = st.session_state.get(list_key)
    if not qs: return
    
    q = qs[index]
    unique_id = q.db_uuid or q.id
    
    if action == 'select':
        sel_val = st.session_state.get(f"{key_prefix}_sel_{unique_id}")
        if sel_val:
            q.is_selected = True
            q.is_rejected = False
            # Force update Reject checkbox
            st.session_state[f"{key_prefix}_rej_{unique_id}"] = False
        else:
            q.is_selected = False
            
    elif action == 'reject':
        rej_val = st.session_state.get(f"{key_prefix}_rej_{unique_id}")
        if rej_val:
            q.is_rejected = True
            q.is_selected = False
            # Force update Select checkbox
            st.session_state[f"{key_prefix}_sel_{unique_id}"] = False
        else:
            q.is_rejected = False

def regenerate_callback(q, key_prefix, custom_blueprint=None):
    """Callback for regeneration with optional custom configuration"""
    try:
        blueprint = custom_blueprint if custom_blueprint else q.question_blueprint
        manager = st.session_state.manager

        # Execute regeneration
        new_q = asyncio.run(manager.regenerate_question(blueprint))

        if new_q:
             # Update Object
             q.question_english = new_q.question_english
             q.options_english = new_q.options_english
             q.answer = new_q.answer
             q.question_hindi = new_q.question_hindi
             q.options_hindi = new_q.options_hindi

             # Update blueprint if custom
             if custom_blueprint:
                 q.question_blueprint = custom_blueprint

             # Reset Status and Feedback
             q.is_selected = False
             q.is_rejected = False
             q.user_feedback = ""

             unique_id = q.db_uuid or q.id

             # Update Session State Keys for Content
             if f"{key_prefix}_q_eng_{unique_id}" in st.session_state:
                 st.session_state[f"{key_prefix}_q_eng_{unique_id}"] = new_q.question_english
             for i, opt in enumerate(new_q.options_english):
                 if f"{key_prefix}_opt_eng_{unique_id}_{i}" in st.session_state:
                     st.session_state[f"{key_prefix}_opt_eng_{unique_id}_{i}"] = opt
             if f"{key_prefix}_ans_{unique_id}" in st.session_state:
                 st.session_state[f"{key_prefix}_ans_{unique_id}"] = new_q.answer

             # Update Session State Keys for Status/Feedback
             if f"{key_prefix}_sel_{unique_id}" in st.session_state:
                 st.session_state[f"{key_prefix}_sel_{unique_id}"] = False
             if f"{key_prefix}_rej_{unique_id}" in st.session_state:
                 st.session_state[f"{key_prefix}_rej_{unique_id}"] = False
             if f"{key_prefix}_fb_{unique_id}" in st.session_state:
                 st.session_state[f"{key_prefix}_fb_{unique_id}"] = ""

        else:
             print("Regeneration returned None")
    except Exception as e:
        print(f"Regeneration callback error: {e}")

# --- Helper Functions ---

def auto_distribute_empty_fields(config_list):
    """Automatically distribute questions when fields are empty.

    Creates a combined distribution where each question gets a unique combination
    of topic, pattern, cognitive level, and difficulty - cycling through options.

    For large tests (>50 questions), uses UPSC-like distribution.
    For small tests, distributes evenly across different types.
    """
    # Validate input
    if not config_list:
        return []

    if not isinstance(config_list, list):
        raise TypeError("config_list must be a list")

    # Available options
    syllabus_subjects = list(syllabus.keys())

    # Pattern types in order of typical UPSC frequency
    pattern_types = [
        "Standard Single-Correct",
        "Multiple-Statement-2 (Correct)",
        "Multiple-Statement-3 (Correct)",
        "Standard Single-Incorrect",
        "Multiple-Statement-2 (Incorrect)",
        "Multiple-Statement-3 (Incorrect)",
        "Std 2-Stmt Assertion-Reason",
        "Multiple-Statement-4 (Correct)",
        "Multiple-Statement-4 (Incorrect)",
        "How Many - Statement",
        "Complex 3-Stmt Assertion-Reason",
        "Chronological Ordering",
        "Geographical Sequencing"
    ]

    cognitive_levels = [
        "Comprehension/Conceptual",
        "Application/Analysis",
        "Recall/Recognition",
        "Higher Reasoning/Synthesis"
    ]

    difficulty_levels = ["Moderate", "Difficult", "Easy"]

    # UPSC-like distribution for large tests (percentages)
    # General distribution (100% baseline):
    # - How Many Statements: 30%
    # - Multiple Statements (3/4 stmt, 70/30 correct/incorrect): 20%
    # - Assertion-Reason (60/40 2-stmt/3-stmt): 20%
    # - Two Statements (Multiple-Statement-2): 10%
    # - Matching pairs (60/40 how many/which): 10%
    # - Standard Single Correct: 10%
    UPSC_PATTERN_DIST = {
        "How Many - Statement": 30,
        "Multiple-Statement-3 (Correct)": 10,          # 20% MS3/4 total
        "Multiple-Statement-4 (Correct)": 4,           # 70% correct
        "Multiple-Statement-3 (Incorrect)": 4,         # 30% incorrect
        "Multiple-Statement-4 (Incorrect)": 2,
        "Std 2-Stmt Assertion-Reason": 12,             # 20% A-R total, 60% 2-stmt
        "Complex 3-Stmt Assertion-Reason": 8,          # 40% 3-stmt
        "Multiple-Statement-2 (Correct)": 7,           # 10% MS2 total
        "Multiple-Statement-2 (Incorrect)": 3,         # 70/30 split
        "How Many Pairs Correct/Incorrect": 6,         # 10% matching total
        "How Many Sets/Triplets": 4,                   # 60/40 split
        "Standard Single-Correct": 10,
        "Chronological Ordering": 0,                   # Added per subject
        "Geographical Sequencing": 0,                  # Added per subject
        "Standard Single-Incorrect": 0
    }

    UPSC_COGNITIVE_DIST = {
        "Comprehension/Conceptual": 40,
        "Application/Analysis": 30,
        "Recall/Recognition": 20,
        "Higher Reasoning/Synthesis": 10
    }

    UPSC_DIFFICULTY_DIST = {
        "Moderate": 50,
        "Difficult": 35,
        "Easy": 15
    }
    def get_distribution(total_count, options, upsc_dist=None, subject=None):
        """Get list of options distributed across total_count questions.

        Args:
            total_count: Number of questions to generate
            options: List of available options
            upsc_dist: Base distribution dictionary
            subject: Subject name for subject-specific adjustments (History/Geography)
        """
        num_options = len(options)

        if upsc_dist:
            # Use weighted UPSC-like percentage distribution
            # Apply subject-specific adjustments
            working_dist = dict(upsc_dist)  # Copy to avoid modifying original

            # Subject-specific pattern adjustments
            if subject and subject.lower() == "history":
                # History: Add 20% Chronological Ordering, scale others by 0.8 (100%->80%)
                scale_factor = 0.8
                for key in working_dist:
                    if key != "Chronological Ordering":
                        working_dist[key] = round(working_dist[key] * scale_factor, 1)
                working_dist["Chronological Ordering"] = 20
            elif subject and subject.lower() == "geography":
                # Geography: Add 15% Geo Sequencing, scale others by 0.85 (100%->85%)
                scale_factor = 0.85
                for key in working_dist:
                    if key not in ["Geographical Sequencing", "Chronological Ordering"]:
                        working_dist[key] = round(working_dist[key] * scale_factor, 1)
                working_dist["Geographical Sequencing"] = 15
                # Chronological can still appear in Geography but not mandated
            else:
                # Other subjects: Chronological can appear (5%)
                if "Chronological Ordering" in working_dist:
                    scale_factor = 0.95
                    for key in working_dist:
                        if key != "Chronological Ordering":
                            working_dist[key] = round(working_dist[key] * scale_factor, 1)
                    working_dist["Chronological Ordering"] = 5

            result = []
            remaining = total_count
            items = list(working_dist.items())

            # Filter out patterns with 0 percentage
            items = [(option, percentage) for option, percentage in items if percentage > 0]

            # Sort by percentage descending to prioritize high-percentage items
            items.sort(key=lambda x: x[1], reverse=True)

            # First pass: allocate based on percentages
            allocated = {}
            for option, percentage in items:
                count = round(total_count * percentage / 100)
                count = min(count, remaining)
                allocated[option] = count
                remaining -= count

            # Second pass: distribute remaining questions to highest percentage items
            # that haven't reached their theoretical maximum
            if remaining > 0:
                for option, percentage in items:
                    if remaining <= 0:
                        break
                    # Calculate theoretical maximum (rounded up)
                    theoretical_max = int(total_count * percentage / 100) + 1
                    if allocated[option] < theoretical_max:
                        allocated[option] += 1
                        remaining -= 1

            # Build result list
            for option, count in allocated.items():
                if count > 0:
                    result.extend([option] * count)

            return result
        else:
            # Fallback: distribute evenly across options (for topics, cognitive, difficulty)
            # Use random selection to avoid bias toward first items in list
            result = []

            # Calculate base count per option and remainder
            base_count = total_count // num_options
            remainder = total_count % num_options

            # Create a shuffled list of options
            shuffled_options = list(options)
            random.shuffle(shuffled_options)

            # Distribute: some options get base_count+1, others get base_count
            for i, option in enumerate(shuffled_options):
                count = base_count + (1 if i < remainder else 0)
                result.extend([option] * count)

            # Shuffle the final result to mix up the order
            random.shuffle(result)
            return result

    # Main processing logic
    result = []

    for item in config_list:
        total_count = item['count']
        if total_count <= 0:
            continue

        # Determine what needs randomization
        randomize_topic = item.get('_randomize_topic', False)
        randomize_pattern = item.get('_randomize_pattern', False)
        randomize_cognitive = item.get('_randomize_cognitive', False)
        randomize_difficulty = item.get('_randomize_difficulty', False)

        # Get distributions for each field that needs randomization
        if randomize_topic:
            topics = get_distribution(total_count, syllabus_subjects)
        else:
            topics = [item.get('topic', '')] * total_count

        if randomize_cognitive:
            cognitives = get_distribution(total_count, cognitive_levels, UPSC_COGNITIVE_DIST)
        else:
            cognitives = [item.get('cognitive')] * total_count

        if randomize_difficulty:
            difficulties = get_distribution(total_count, difficulty_levels, UPSC_DIFFICULTY_DIST)
        else:
            difficulties = [item.get('difficulty')] * total_count

        # For patterns, we need to handle topic-specific distributions
        if randomize_pattern:
            # When both topic and pattern are randomized, we need subject-specific pattern distribution
            if randomize_topic:
                # For small counts, use a global weighted distribution instead of per-subject
                # to avoid skewing when each subject gets only 1-2 questions
                if total_count < 20:
                    # Use general distribution (with 5% chronological for mixed subjects)
                    patterns = get_distribution(total_count, pattern_types, UPSC_PATTERN_DIST, "Mixed")
                else:
                    # For larger counts, use subject-specific distributions
                    topic_counts = Counter(topics)

                    patterns = []
                    for subject_name, subject_count in topic_counts.items():
                        # Get pattern distribution for this subject
                        subject_patterns = get_distribution(subject_count, pattern_types, UPSC_PATTERN_DIST, subject_name)
                        patterns.extend(subject_patterns)

                    # Shuffle patterns to mix them up (otherwise they'll be grouped by subject)
                    random.shuffle(patterns)
            else:
                # Topic is fixed, extract subject for pattern distribution
                topic_str = item.get('topic', '')
                subject = None
                if topic_str:
                    # Extract subject from topic string
                    # Handle formats: "Geography", "Geography: Subtopic", "Indian geography", etc.
                    topic_lower = topic_str.lower()

                    # Check if topic contains any of our main subjects
                    if 'geography' in topic_lower:
                        subject = 'Geography'
                    elif 'history' in topic_lower:
                        subject = 'History'
                    elif 'polity' in topic_lower:
                        subject = 'Polity'
                    elif 'economy' in topic_lower or 'economic' in topic_lower:
                        subject = 'Economy'
                    elif 'environment' in topic_lower or 'ecology' in topic_lower:
                        subject = 'Environment'
                    elif 'science' in topic_lower or 'technology' in topic_lower or 'tech' in topic_lower:
                        subject = 'Science & Tech'
                    elif 'current affairs' in topic_lower:
                        subject = 'Current Affairs'
                    else:
                        # Fallback: try to extract from "Subject: Subtopic" format
                        subject = topic_str.split(':')[0].strip() if ':' in topic_str else topic_str.strip()

                patterns = get_distribution(total_count, pattern_types, UPSC_PATTERN_DIST, subject)
        else:
            patterns = [item.get('pattern')] * total_count

        # Create individual question configs
        for i in range(total_count):
            try:
                result.append({
                    'topic': topics[i] if i < len(topics) and topics[i] else '',
                    'pattern': patterns[i] if i < len(patterns) and patterns[i] else 'Standard Single-Correct',
                    'cognitive': cognitives[i] if i < len(cognitives) and cognitives[i] else 'Comprehension/Conceptual',
                    'difficulty': difficulties[i] if i < len(difficulties) and difficulties[i] else 'Moderate',
                    'count': 1
                })
            except (IndexError, KeyError) as e:
                # Skip malformed items but continue processing
                continue

    return result

def get_config_table(key_suffix):
    """Reusable config table for different modes"""

    # Use "Randomize" as a valid option that triggers auto-distribution
    RANDOMIZE_MARKER = "🎲 Randomize"

    fmt_options = [
        RANDOMIZE_MARKER,
        "Standard Single-Correct",
        "Standard Single-Incorrect",
        "Multiple-Statement-2 (Correct)",
        "Multiple-Statement-3 (Correct)",
        "Multiple-Statement-4 (Correct)",
        "Multiple-Statement-2 (Incorrect)",
        "Multiple-Statement-3 (Incorrect)",
        "Multiple-Statement-4 (Incorrect)",
        "How Many - Statement",
        "How Many Pairs Correct/Incorrect",
        "How Many Sets/Triplets",
        "Std 2-Stmt Assertion-Reason",
        "Complex 3-Stmt Assertion-Reason",
        "Chronological Ordering",
        "Geographical Sequencing"
    ]
    cplx_options = [
        RANDOMIZE_MARKER,
        "Recall/Recognition",
        "Comprehension/Conceptual",
        "Application/Analysis",
        "Higher Reasoning/Synthesis"
    ]
    diff_options = [RANDOMIZE_MARKER, "Easy", "Moderate", "Difficult"]

    # Build flat topic list from syllabus for the topic finder
    topic_search_options = [""]  # Empty option first
    for subject in syllabus.keys():
        topic_search_options.append(subject)
    for subject, topics in syllabus.items():
        for topic in topics:
            topic_search_options.append(f"{subject}: {topic}")

    if f'config_df_{key_suffix}' not in st.session_state:
        # Default row with empty topic (randomized)
        st.session_state[f'config_df_{key_suffix}'] = pd.DataFrame([
            {
                "Topic": "",
                "Pattern": RANDOMIZE_MARKER,
                "Cognitive": RANDOMIZE_MARKER,
                "Difficulty": RANDOMIZE_MARKER,
                "Count": 5
            }
        ])

    st.markdown("### Configuration Table")

    # Topic finder - searchable dropdown for reference
    st.selectbox(
        "🔍 Topic Finder (type to search)",
        options=topic_search_options,
        index=0,
        key=f"topic_finder_{key_suffix}",
        help="Search for topics here, then type in the Topic column below. Leave Topic empty to randomize."
    )

    column_config = {
        "Topic": st.column_config.TextColumn("Topic", default="", width="medium", help="Leave empty to randomize across subjects, or type any topic"),
        "Pattern": st.column_config.SelectboxColumn("Pattern", options=fmt_options, default=RANDOMIZE_MARKER, required=False, width="medium"),
        "Cognitive": st.column_config.SelectboxColumn("Cognitive Level", options=cplx_options, default=RANDOMIZE_MARKER, required=False, width="medium"),
        "Difficulty": st.column_config.SelectboxColumn("Difficulty", options=diff_options, default=RANDOMIZE_MARKER, required=False, width="small"),
        "Count": st.column_config.NumberColumn("Count", min_value=1, max_value=100, step=1, default=5, required=True, width="small"),
    }

    edited_df = st.data_editor(
        st.session_state[f'config_df_{key_suffix}'],
        column_config=column_config,
        num_rows="dynamic",
        key=f"editor_{key_suffix}",
        width="stretch",
        hide_index=True
    )

    # Add duplicate row buttons
    if not edited_df.empty:
        col_dup1, col_dup2, col_dup3 = st.columns([1, 1, 2])
        with col_dup1:
            if st.button("➕ Duplicate Last Row", key=f"duplicate_last_{key_suffix}"):
                # Duplicate the last row
                last_row = edited_df.iloc[-1].to_dict()
                new_df = pd.concat([edited_df, pd.DataFrame([last_row])], ignore_index=True)
                st.session_state[f'config_df_{key_suffix}'] = new_df
                st.rerun()

        with col_dup2:
            row_to_duplicate = st.number_input(
                "Row to duplicate:",
                min_value=1,
                max_value=len(edited_df),
                value=1,
                step=1,
                key=f"row_select_{key_suffix}"
            )

        with col_dup3:
            if st.button(f"📋 Duplicate Row #{row_to_duplicate}", key=f"duplicate_selected_{key_suffix}"):
                # Duplicate the selected row
                row_idx = row_to_duplicate - 1  # Convert to 0-indexed
                if 0 <= row_idx < len(edited_df):
                    selected_row = edited_df.iloc[row_idx].to_dict()
                    new_df = pd.concat([edited_df, pd.DataFrame([selected_row])], ignore_index=True)
                    st.session_state[f'config_df_{key_suffix}'] = new_df
                    st.rerun()

    # Check for randomized fields and show summary
    if not edited_df.empty:
        randomize_topic = edited_df['Topic'].isna().sum() + (edited_df['Topic'] == '').sum()
        randomize_pattern = (edited_df['Pattern'] == RANDOMIZE_MARKER).sum() + edited_df['Pattern'].isna().sum()
        randomize_cognitive = (edited_df['Cognitive'] == RANDOMIZE_MARKER).sum() + edited_df['Cognitive'].isna().sum()
        randomize_difficulty = (edited_df['Difficulty'] == RANDOMIZE_MARKER).sum() + edited_df['Difficulty'].isna().sum()

        randomized_fields = []
        if randomize_topic > 0:
            randomized_fields.append("Topics")
        if randomize_pattern > 0:
            randomized_fields.append("Patterns")
        if randomize_cognitive > 0:
            randomized_fields.append("Cognitive")
        if randomize_difficulty > 0:
            randomized_fields.append("Difficulty")

        if randomized_fields:
            st.info(f"🎲 Auto-distributing: {', '.join(randomized_fields)}")

    # Convert to list of dicts - mark randomize fields for distribution
    config_list = []
    if not edited_df.empty:
        for _, row in edited_df.iterrows():
            count = row.get('Count', 0)
            if pd.isna(count) or count <= 0:
                continue

            # Check which fields should be randomized (empty = randomize)
            topic = row.get('Topic', '')
            topic = topic.strip() if pd.notna(topic) and topic else ''
            topic_randomize = not topic  # Empty topic means randomize

            pattern = row.get('Pattern')
            pattern_randomize = pd.isna(pattern) or not pattern or pattern == RANDOMIZE_MARKER

            cognitive = row.get('Cognitive')
            cognitive_randomize = pd.isna(cognitive) or not cognitive or cognitive == RANDOMIZE_MARKER

            difficulty = row.get('Difficulty')
            difficulty_randomize = pd.isna(difficulty) or not difficulty or difficulty == RANDOMIZE_MARKER

            config_list.append({
                "topic": topic if not topic_randomize else "",  # Empty string signals randomization
                "pattern": pattern if not pattern_randomize else None,
                "cognitive": cognitive if not cognitive_randomize else None,
                "difficulty": difficulty if not difficulty_randomize else None,
                "count": int(count),
                # Track which fields need randomization
                "_randomize_topic": topic_randomize,
                "_randomize_pattern": pattern_randomize,
                "_randomize_cognitive": cognitive_randomize,
                "_randomize_difficulty": difficulty_randomize
            })

    # Show warning for empty config
    if not config_list:
        st.warning("No valid rows in configuration. Add at least one row with Count > 0.")

    # Auto-distribute empty fields
    if config_list:
        config_list = auto_distribute_empty_fields(config_list)

    # Preview Distribution - show what will actually be generated
    if config_list:
        with st.expander("📊 Preview Distribution", expanded=False):
            # Add shuffle button at the top
            col_metric, col_shuffle = st.columns([2, 1])
            with col_metric:
                total_questions = sum(item['count'] for item in config_list)
                st.metric("Total Questions", total_questions)
            with col_shuffle:
                if st.button("🔀 Shuffle Preview", key="shuffle_preview_advanced"):
                    # Force regeneration by incrementing a counter
                    if 'preview_shuffle_count_adv' not in st.session_state:
                        st.session_state.preview_shuffle_count_adv = 0
                    st.session_state.preview_shuffle_count_adv += 1
                    st.rerun()

            # Group by topic for summary
            topic_counts = {}
            pattern_counts = {}
            cognitive_counts = {}
            difficulty_counts = {}

            for item in config_list:
                topic = item.get('topic', '') or 'Mixed'
                pattern = item.get('pattern', 'Mixed')
                cognitive = item.get('cognitive', 'Mixed')
                difficulty = item.get('difficulty', 'Mixed')
                count = item['count']

                topic_counts[topic] = topic_counts.get(topic, 0) + count
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + count
                cognitive_counts[cognitive] = cognitive_counts.get(cognitive, 0) + count
                difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + count

            # Display in columns
            prev_col1, prev_col2 = st.columns(2)

            with prev_col1:
                st.markdown("**By Topic:**")
                for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
                    display_topic = topic if topic else "Mixed/Randomized"
                    st.text(f"  {display_topic}: {count}")

                st.markdown("**By Pattern:**")
                for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
                    st.text(f"  {pattern}: {count}")

            with prev_col2:
                st.markdown("**By Cognitive Level:**")
                for cognitive, count in sorted(cognitive_counts.items(), key=lambda x: -x[1]):
                    st.text(f"  {cognitive}: {count}")

                st.markdown("**By Difficulty:**")
                for difficulty, count in sorted(difficulty_counts.items(), key=lambda x: -x[1]):
                    st.text(f"  {difficulty}: {count}")

            # Detailed breakdown table
            st.markdown("---")
            st.markdown("**Detailed Breakdown:**")

            # Shuffle the order for display
            shuffled_config = list(config_list)
            random.shuffle(shuffled_config)

            preview_data = []
            for i, item in enumerate(shuffled_config):
                preview_data.append({
                    "#": i + 1,
                    "Topic": item.get('topic', '') or '🎲',
                    "Pattern": item.get('pattern', '🎲'),
                    "Difficulty": item.get('difficulty', '🎲')
                })
            st.dataframe(pd.DataFrame(preview_data), width="stretch", hide_index=True)

    return config_list

def generate_blueprint_template():
    """Generates a sample Excel blueprint template."""
    df = pd.read_excel('./prompts/blueprint_template.xlsx')
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Blueprint')
    output.seek(0)
    return output

def parse_blueprint(uploaded_file):
    """Parses uploaded blueprint to text context."""
    text = ""
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
            text = df.to_string(index=False)
        else:
            st.error(f"Error: Only xlsx supported.")
    except Exception as e:
        st.error(f"Error parsing blueprint: {e}")
    return text

def render_question_editor(q, index, total_questions, list_key, key_prefix):
    """
    Renders a single question editor block.
    """
    # Use key_prefix for widgets
    with st.container(border=True):
        col_top, col_act = st.columns([0.7, 0.3])
        with col_top:
            # Always show dynamic number based on index
            st.markdown(f"#### Q{index+1} (ID: {q.id})")
        with col_act:
            # Reorder Buttons
            c_up, c_down = st.columns(2)
            with c_up:
                if index > 0:
                    st.button("⬆️", key=f"{key_prefix}_up_{q.db_uuid or q.id}", 
                              on_click=move_question, args=(list_key, index, -1))
            with c_down:
                if index < total_questions - 1:
                    st.button("⬇️", key=f"{key_prefix}_down_{q.db_uuid or q.id}", 
                              on_click=move_question, args=(list_key, index, 1))

        # Content Columns: English (Editable) vs Hindi (View/Auto-update)
        c1, c2 = st.columns(2)
        
        with c1:
            st.caption("English (Editable)")
            new_q_eng = st.text_area("Question Text", q.question_english, height='content', key=f"{key_prefix}_q_eng_{q.db_uuid or q.id}")
            
            # Options
            new_opts_eng = []
            for i, opt in enumerate(q.options_english):
                val = st.text_area(f"({chr(97+i)})", opt, height='content', key=f"{key_prefix}_opt_eng_{q.db_uuid or q.id}_{i}")
                new_opts_eng.append(val)
                
            new_ans = st.selectbox("Answer", ['A','B','C','D'], index=['A','B','C','D'].index(q.answer), key=f"{key_prefix}_ans_{q.db_uuid or q.id}")
            
            # Update Object state immediately for these fields
            q.question_english = new_q_eng
            q.options_english = new_opts_eng
            q.answer = new_ans

            st.markdown("---")
            if st.button("🔄 Update Edits...", key=f"{key_prefix}_trans_{q.db_uuid or q.id}"):
                with st.spinner("Translating..."):
                    try:
                        q_hindi_obj = asyncio.run(manager.translate_single_question(q.question_english, q.options_english))
                        if q_hindi_obj:
                            q.question_hindi = q_hindi_obj.question
                            q.options_hindi = q_hindi_obj.options
                            st.success("Translated!")
                            st.rerun()
                        else:
                            st.error("Translation returned empty.")
                    except Exception as e:
                        st.error(f"Translation failed: {e}")

        with c2:
            st.caption("Hindi Version")
            st.markdown("")
            st.markdown(f"**{q.question_hindi}**")
            for i, opt in enumerate(q.options_hindi):
                st.markdown(f"({chr(97+i)}) {opt}")
            
            

        st.divider()

        # Actions Row - tighter layout
        ac1, ac2, ac3 = st.columns([0.3, 0.75, 0.4])
        with ac1:
            # Two Checkboxes for Status
            st.caption("Status")

            # Ensure session state is synced with object if not set (first run)
            k_sel = f"{key_prefix}_sel_{q.db_uuid or q.id}"
            k_rej = f"{key_prefix}_rej_{q.db_uuid or q.id}"

            if k_sel not in st.session_state: st.session_state[k_sel] = q.is_selected
            if k_rej not in st.session_state: st.session_state[k_rej] = q.is_rejected

            c_s, c_r = st.columns([1, 1], gap="small")
            c_s.checkbox("Select", key=k_sel, on_change=update_selection, args=(list_key, index, 'select', key_prefix))
            c_r.checkbox("Reject", key=k_rej, on_change=update_selection, args=(list_key, index, 'reject', key_prefix))

            # Display current state visually
            if q.is_selected:
                st.markdown('<span class="status-badge status-selected">Selected</span>', unsafe_allow_html=True)
            elif q.is_rejected:
                st.markdown('<span class="status-badge status-rejected">Rejected</span>', unsafe_allow_html=True)

        with ac2:
            # Feedback
            fb = st.text_input("Feedback / Reason (Mandatory)", value=q.user_feedback or "", key=f"{key_prefix}_fb_{q.db_uuid or q.id}")
            q.user_feedback = fb
            if not fb:
                st.caption("⚠️ Feedback required")

        with ac3:
            st.caption("Action")
            st.button("⚡ Regenerate", key=f"{key_prefix}_regen_{q.db_uuid or q.id}",
                      on_click=regenerate_callback, args=(q, key_prefix, None))

def parse_blueprint(blueprint_text):
    """Extract metadata from blueprint text"""
    if not blueprint_text:
        return {"topic": "N/A", "subtopic": "N/A", "pattern": "N/A", "cognitive": "N/A", "difficulty": "N/A"}

    metadata = {"topic": "N/A", "subtopic": "N/A", "pattern": "N/A", "cognitive": "N/A", "difficulty": "N/A"}
    lines = blueprint_text.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith("Topic:"):
            metadata["topic"] = line.replace("Topic:", "").strip()
        elif line.startswith("Subtopic:"):
            metadata["subtopic"] = line.replace("Subtopic:", "").strip()
        elif line.startswith("Format:") or line.startswith("Question Type:"):
            metadata["pattern"] = line.split(":", 1)[1].strip() if ":" in line else "N/A"
        elif line.startswith("Cognitive"):
            metadata["cognitive"] = line.split(":", 1)[1].strip() if ":" in line else "N/A"
        elif line.startswith("Difficulty:"):
            metadata["difficulty"] = line.replace("Difficulty:", "").strip()

    return metadata

def render_review_interface(questions, test_code, list_key='loaded_questions', unsaved=False):
    """
    Renders the review interface for Modify and New Test flows.
    """
    if unsaved:
        st.markdown('<div class="unsaved-warning">⚠️ <strong>Unsaved Test:</strong> This generated test is not yet saved to the database. Review and click "Save to Database" below.</div>', unsafe_allow_html=True)

    # Stats
    total = len(questions)
    selected = sum(1 for q in questions if q.is_selected)
    rejected = sum(1 for q in questions if q.is_rejected)
    pending = total - selected - rejected

    st.metric("Total Questions", total)
    c1, c2, c3 = st.columns(3)
    c1.metric("Selected", selected)
    c2.metric("Rejected", rejected)
    c3.metric("Pending", pending)

    st.divider()

    # Question Metadata Dashboard
    with st.expander("📊 Question Distribution Dashboard", expanded=False):
        st.subheader("Generated Question Metadata")

        # Parse blueprints and create dashboard data
        dashboard_data = []
        for q in questions:
            metadata = parse_blueprint(q.question_blueprint)
            dashboard_data.append({
                "Q#": q.question_number,
                "Subject": q.subject or "N/A",
                "Topic": metadata["topic"],
                "Subtopic": metadata["subtopic"],
                "Pattern": metadata["pattern"],
                "Cognitive": metadata["cognitive"],
                "Difficulty": metadata["difficulty"],
                "Status": "✅ Selected" if q.is_selected else ("❌ Rejected" if q.is_rejected else "⏳ Pending")
            })

        if dashboard_data:
            df = pd.DataFrame(dashboard_data)
            # Calculate appropriate height based on number of rows (header + data rows)
            row_height = 35  # approximate height per row in pixels
            header_height = 38
            min_height = 200
            max_height = 600
            calculated_height = min(max(header_height + (len(df) * row_height), min_height), max_height)

            st.dataframe(df, width='stretch', hide_index=True, height=calculated_height)

            # Summary statistics
            st.subheader("Distribution Summary")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**By Difficulty:**")
                diff_counts = df['Difficulty'].value_counts()
                for diff, count in diff_counts.items():
                    st.write(f"• {diff}: {count}")

            with col2:
                st.write("**By Cognitive Level:**")
                cog_counts = df['Cognitive'].value_counts()
                for cog, count in cog_counts.items():
                    st.write(f"• {cog}: {count}")

            with col3:
                st.write("**By Pattern:**")
                pattern_counts = df['Pattern'].value_counts()
                for pattern, count in pattern_counts.items():
                    st.write(f"• {pattern}: {count}")

    st.divider()

    # Generate Unique Key Prefix for Widgets based on test_code
    # This prevents state collision when switching between tests that have same question IDs (numbers)
    # If test_code contains spaces or special chars, clean it up? 
    unique_prefix = f"{list_key}_{test_code}" if test_code else list_key

    # Question List
    # We must iterate by index for reordering callbacks
    with st.container(height=600, border=True):
        for i in range(len(questions)):
            # Re-fetch q from list in case of reorder
            q = questions[i]
            render_question_editor(q, i, total, list_key, unique_prefix)
    
    st.divider()
    
    # Add More Questions
    with st.expander("➕ Add More Questions"):

        config_list = get_config_table("add_more")

        if st.button("Generate & Append"):
            with st.spinner("Generating additional questions..."):
                start_num = 1
                if questions:
                    start_num = max(q.question_number for q in questions) + 1
                
                # Calculate total num from config
                total_num = sum(c['count'] for c in config_list)
                if total_num == 0:
                     st.error("Please add at least one row with count > 0")
                else:
                    new_qs_obj, _ = asyncio.run(manager.generate_questions(
                        source_text=None, uploaded_pdf=None, topic_input=None, # Topic is in config now
                        question_distribution=config_list,
                        start_question_number=start_num
                    ))
                    
                    if new_qs_obj.questions:
                        questions.extend(new_qs_obj.questions)
                        st.success(f"Added {len(new_qs_obj.questions)} questions! Please review and save.")
                        st.rerun()
    
    st.divider()

    # Save Changes
    c_save, c_dl = st.columns(2)
    with c_save:
        if st.button("💾 Save to Database", type="primary"):
            # Validation
            incomplete = []
            for idx, q in enumerate(questions):
                if not (q.is_selected or q.is_rejected):
                    incomplete.append(f"Q{idx+1}: Status not set")
                if not q.user_feedback:
                    incomplete.append(f"Q{idx+1}: Feedback missing")
            
            if incomplete:
                st.error("Cannot Save! Please resolve the following:\n" + "\n".join(incomplete[:5]))
                if len(incomplete) > 5: st.error(f"...and {len(incomplete)-5} more.")
            else:
                # Ensure sequential numbering based on current list order
                for idx, q in enumerate(questions):
                    q.question_number = idx + 1
                
                success = manager.archivist.save_questions(questions, test_code)
                if success:
                    st.success("Test saved successfully!")
                    if unsaved:
                        st.session_state.is_unsaved_new_test = False
                        st.rerun()
                else:
                    st.error("Failed to save changes.")
    
    with c_dl:
        # Download DOCX
        selected_only_qs = [q for q in questions if q.is_selected]
        if selected_only_qs:
            docx = generate_upsc_docx(selected_only_qs)
            st.download_button("📄 Download Selected (DOCX)", docx, f"{test_code}.docx")
        else:
            st.warning("No selected questions for download.")

# --- Main App ---

# Header with logo
with open("logo.svg", "r") as f:
    light_svg = f.read()
with open("logo-dark.svg", "r") as f:
    dark_svg = f.read()

# Use CSS media query for system theme preference (most reliable)
st.markdown(f'''
<style>
    .logo-light {{ display: block; }}
    .logo-dark {{ display: none; }}
    @media (prefers-color-scheme: dark) {{
        .logo-light {{ display: none; }}
        .logo-dark {{ display: block; }}
    }}
</style>
<div style="width:300px">
    <div class="logo-light">{light_svg}</div>
    <div class="logo-dark">{dark_svg}</div>
</div>
''', unsafe_allow_html=True)

st.caption("Prelims Question Answer Generator")

# Sidebar Mode
mode = st.sidebar.radio("Mode", ["Prelims Test Series", "Random Generation"])

if mode == "Prelims Test Series":
    st.header("Prelims Test Series Management")
    
    # Check if we are reviewing a new test
    if st.session_state.get('is_unsaved_new_test', False):
         st.subheader(f"Review New Test: {st.session_state.current_test_code}")
         if st.button("⬅️ Discard & Back"):
             st.session_state.loaded_questions = None
             st.session_state.current_test_code = None
             st.session_state.is_unsaved_new_test = False
             st.rerun()
             
         if st.session_state.get('loaded_questions'):
             render_review_interface(st.session_state.loaded_questions, st.session_state.current_test_code, 'loaded_questions', unsaved=True)
         else:
             st.error("Error: Questions lost from session.")

    else:
        sub_mode = st.radio("Action", ["Modify Generated Test", "Create New Test"], horizontal=True)
        
        if sub_mode == "Create New Test":
            st.subheader("Create New Test")
            test_code_input = st.text_input("Enter Unique Test Code", placeholder="e.g. 2025-Full-01")
            
            # Check uniqueness
            if test_code_input:
                exists = manager.archivist.check_test_code_exists(test_code_input.strip())
                if exists:
                    st.error("Test Code already exists! Please choose another.")
                if test_code_input.strip()=="":
                    st.error("Test Code cannot be empty or just spaces.")
                else:
                    st.success("Test Code is available.")
                    
                    test_type = st.radio("Test Type", ["Full Length", "Sectional"])
                    
                    subject_topic = None
                    if test_type == "Sectional":
                        subject = st.selectbox("Select Subject", list(syllabus.keys()))
                        topic_options = ["All Topics"] + syllabus[subject]
                        topic = st.selectbox("Select Topic", topic_options)
                        if topic == "All Topics":
                            subject_topic = subject
                        else:
                            subject_topic = topic
                    
                    # Blueprint Logic
                    blueprint_mode = st.radio("Blueprint Source", ["Default Blueprint", "Upload Custom Blueprint", "Configure via UI"])
                    
                    uploaded_bp_text = None
                    uploaded_bp_file = None
                    ui_config_list = []
                    
                    if blueprint_mode == "Upload Custom Blueprint":
                        st.info("Download the template, edit it, and upload.")
                        # Download Template
                        tpl = generate_blueprint_template()
                        st.download_button("📥 Download Excel Template", tpl, "blueprint_template.xlsx")
                        
                        uploaded_bp_file = st.file_uploader("Upload Blueprint (Excel)", type=['xlsx'])
                        if uploaded_bp_file:
                            if uploaded_bp_file.name.endswith('.xlsx'):
                                try:
                                    df_bp = pd.read_excel(uploaded_bp_file)
                                    uploaded_bp_text = df_bp.to_string(index=False)
                                    st.success("Blueprint Loaded")
                                except Exception as e:
                                    st.error(f"Error reading Excel: {e}")
                            else:
                                uploaded_bp_file = uploaded_bp_file # Pass to manager as is for docx
                    
                    elif blueprint_mode == "Configure via UI":
                        st.info("Define the test blueprint using the table below.")
                        ui_config_list = get_config_table("create_test")

                        ui_table_sum = sum(item['count'] for item in ui_config_list)
                    
                    # Number of Questions
                    if test_type == "Sectional" and blueprint_mode == "Configure via UI":
                        num_q = ui_table_sum
                        st.info(f"Number of Questions set to {num_q} based on the UI configuration.")
                    else:
                        num_q = st.number_input("Number of Questions", 1, 100, 100 if test_type == "Full Length" else 20)

                    # Preview Distribution
                    if num_q > 0:
                        st.markdown("### Preview Distribution")

                        # Build preview config based on blueprint mode
                        preview_config = []

                        if blueprint_mode == "Configure via UI" and ui_config_list:
                            preview_config = ui_config_list.copy()
                            # Auto-fill remainder if needed
                            if ui_table_sum < num_q:
                                remainder = num_q - ui_table_sum
                                rem_topic = subject_topic if test_type == "Sectional" else ""
                                preview_config.append({
                                    "topic": rem_topic,
                                    "pattern": None,  # Randomize patterns
                                    "cognitive": None,  # Randomize cognitive
                                    "difficulty": None,  # Randomize difficulty
                                    "count": remainder,
                                    "_randomize_topic": not rem_topic,
                                    "_randomize_pattern": True,
                                    "_randomize_cognitive": True,
                                    "_randomize_difficulty": True
                                })
                        elif blueprint_mode == "Default Blueprint":
                            # Use weighted distribution instead of loading Excel file
                            preview_config = [{
                                "topic": subject_topic if test_type == "Sectional" and subject_topic else "",
                                "pattern": None,
                                "cognitive": None,
                                "difficulty": None,
                                "count": num_q,
                                "_randomize_topic": not (test_type == "Sectional" and subject_topic),
                                "_randomize_pattern": True,
                                "_randomize_cognitive": True,
                                "_randomize_difficulty": True
                            }]
                        elif blueprint_mode == "Upload Custom Blueprint" and uploaded_bp_file:
                            try:
                                df_bp = pd.read_excel(uploaded_bp_file)
                                preview_config = parse_blueprint_config(df_bp=df_bp)

                                bp_sum = sum(item['count'] for item in preview_config)
                                if bp_sum < num_q:
                                    remainder = num_q - bp_sum
                                    rem_topic = subject_topic if test_type == "Sectional" else ""
                                    preview_config.append({
                                        "topic": rem_topic,
                                        "pattern": None,  # Randomize patterns
                                        "cognitive": None,  # Randomize cognitive
                                        "difficulty": None,  # Randomize difficulty
                                        "count": remainder,
                                        "_randomize_topic": not rem_topic,
                                        "_randomize_pattern": True,
                                        "_randomize_cognitive": True,
                                        "_randomize_difficulty": True
                                    })
                            except Exception as e:
                                st.warning(f"Could not parse uploaded blueprint for preview: {e}")
                        else:
                            # Default: create a single config entry with randomization
                            preview_config = [{
                                "topic": subject_topic if test_type == "Sectional" and subject_topic else "",
                                "pattern": None,  # Set to None to trigger randomization
                                "cognitive": None,  # Set to None to trigger randomization
                                "difficulty": None,  # Set to None to trigger randomization
                                "count": num_q,
                                "_randomize_topic": not (test_type == "Sectional" and subject_topic),
                                "_randomize_pattern": True,
                                "_randomize_cognitive": True,
                                "_randomize_difficulty": True
                            }]

                        # Use auto_distribute_empty_fields to get the actual distribution
                        if preview_config:
                            expanded_config = auto_distribute_empty_fields(preview_config)

                            if expanded_config:
                                # Shuffle the order to show questions in random order
                                random.shuffle(expanded_config)

                                # Generate preview data from expanded config
                                preview_data = []
                                for i, item in enumerate(expanded_config):
                                    preview_data.append({
                                        "#": i + 1,
                                        "Topic": item.get('topic', 'N/A')[:30],
                                        "Pattern": item.get('pattern', 'N/A')[:35],
                                        "Cognitive": item.get('cognitive', 'N/A')[:25],
                                        "Difficulty": item.get('difficulty', 'N/A')
                                    })

                                # Display preview table
                                preview_df = pd.DataFrame(preview_data)
                                st.dataframe(preview_df, width="stretch", height=300)

                                # Add shuffle button
                                if st.button("🔀 Shuffle Preview", key="shuffle_fulltest_preview"):
                                    st.rerun()

                                # Show distribution summary
                                st.markdown("**Distribution Summary:**")
                                pattern_counts = {}
                                for item in expanded_config:
                                    pattern = item.get('pattern', 'Unknown')
                                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

                                summary_col1, summary_col2 = st.columns(2)
                                with summary_col1:
                                    for i, (pattern, count) in enumerate(sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)):
                                        if i < len(pattern_counts) // 2 + 1:
                                            st.text(f"• {pattern}: {count}")
                                with summary_col2:
                                    for i, (pattern, count) in enumerate(sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)):
                                        if i >= len(pattern_counts) // 2 + 1:
                                            st.text(f"• {pattern}: {count}")

                    # Generate Button
                    if st.button("Generate Test", type="primary"):
                        # Calculate table sum if needed
                        ui_table_sum = sum(item['count'] for item in ui_config_list) if blueprint_mode == "Configure via UI" else 0

                        if test_type == "Sectional" and not subject_topic:
                            st.error("Subject is required for Sectional Test.")
                        elif not test_code_input.strip():
                            st.error("Test Code cannot be empty or just spaces.")
                        elif blueprint_mode == "Upload Custom Blueprint" and not (uploaded_bp_file or uploaded_bp_text):
                            st.error("Please upload a blueprint file.")
                        elif blueprint_mode == "Configure via UI" and not ui_config_list:
                            st.error("Please add at least one row in the configuration table.")
                        elif blueprint_mode == "Configure via UI" and ui_table_sum != num_q:
                            st.error(f"Error: The total questions in the table ({ui_table_sum}) must exactly match the requested Number of Questions ({num_q}).")
                        else:
                            with st.status("Generating Test...", expanded=True) as status:
                                try:
                                    status.write("Planning...")
                                    
                                    config_list = []
                                    source_txt = None
                                    
                                    if blueprint_mode == "Configure via UI":
                                        # Copy user rows
                                        for item in ui_config_list:
                                            config_list.append(item)
                                        
                                        # Auto-fill remainder based on num_q
                                        if ui_table_sum < num_q:
                                            remainder = num_q - ui_table_sum
                                            rem_topic = subject_topic if test_type == "Sectional" else ""
                                            config_list.append({
                                                "topic": rem_topic,
                                                "pattern": None,
                                                "cognitive": None,
                                                "difficulty": None,
                                                "count": remainder,
                                                "_randomize_topic": not rem_topic,
                                                "_randomize_pattern": True,
                                                "_randomize_cognitive": True,
                                                "_randomize_difficulty": True
                                            })
                                            
                                    elif blueprint_mode == "Default Blueprint":
                                        # Use weighted distribution instead of loading Excel file
                                        config_list = [{
                                            "topic": subject_topic if subject_topic else "",
                                            "pattern": None,
                                            "cognitive": None,
                                            "difficulty": None,
                                            "count": num_q,
                                            "_randomize_topic": not subject_topic,
                                            "_randomize_pattern": True,
                                            "_randomize_cognitive": True,
                                            "_randomize_difficulty": True
                                        }]
                                            
                                    elif blueprint_mode == "Upload Custom Blueprint":
                                        if uploaded_bp_file:
                                             df_bp = pd.read_excel(uploaded_bp_file)
                                             config_list = parse_blueprint_config(df_bp=df_bp)
                                             
                                             # Validation & Auto-fill for Blueprint
                                             bp_sum = sum(item['count'] for item in config_list)
                                             if bp_sum > num_q:
                                                 st.error(f"Error: The total questions in the uploaded blueprint ({bp_sum}) exceeds the requested Number of Questions ({num_q}).")
                                                 st.stop()
                                             elif bp_sum < num_q:
                                                 remainder = num_q - bp_sum
                                                 rem_topic = subject_topic if test_type == "Sectional" else ""
                                                 config_list.append({
                                                     "topic": rem_topic,
                                                     "pattern": None,
                                                     "cognitive": None,
                                                     "difficulty": None,
                                                     "count": remainder,
                                                     "_randomize_topic": not rem_topic,
                                                     "_randomize_pattern": True,
                                                     "_randomize_cognitive": True,
                                                     "_randomize_difficulty": True
                                                 })
                                    
                                    if not config_list:
                                        if num_q > 0:
                                             config_list = [{
                                                 "topic": subject_topic if subject_topic else "",
                                                 "pattern": None,
                                                 "cognitive": None,
                                                 "difficulty": None,
                                                 "count": num_q,
                                                 "_randomize_topic": not subject_topic,
                                                 "_randomize_pattern": True,
                                                 "_randomize_cognitive": True,
                                                 "_randomize_difficulty": True
                                             }]
                                    
                                    # Override total questions if config provided?
                                    # The config sums up to total questions.
                                    # If user entered Num Questions separately, we might want to respect config.
                                    # Let's ignore num_q input if config is present, or validate.
                                    
                                    questions_obj, usage = asyncio.run(manager.generate_questions(
                                        source_text=None,
                                        uploaded_pdf=None, # Pass docx if no text
                                        topic_input=subject_topic if test_type == "Sectional" else None,
                                        question_distribution=config_list
                                    ))
                                    
                                    if questions_obj.questions:
                                        # DO NOT SAVE YET. Load into session.
                                        status.write("Finalizing Preview...")
                                        st.session_state.loaded_questions = questions_obj.questions
                                        st.session_state.current_test_code = test_code_input
                                        st.session_state.is_unsaved_new_test = True
                                        status.update(label="Generation Complete!", state="complete")
                                        st.rerun()
                                    else:
                                        st.error("No questions generated.")
                                except Exception as e:
                                    st.error(f"Error: {e}")
                                    import traceback
                                    st.error(traceback.format_exc())

        elif sub_mode == "Modify Generated Test":
            st.subheader("Modify / Review Test")
            test_codes = manager.archivist.get_unique_test_codes()
            selected_code = st.selectbox("Select Test Code", ['--choose--']+test_codes)
            
            if selected_code:
                # Load questions logic (similar to before)
                if 'current_test_code' not in st.session_state or st.session_state.current_test_code != selected_code:
                    raw_qs = manager.archivist.get_questions_by_test_code(selected_code)
                    loaded_qs = []
                    for qd in raw_qs:
                        try:
                            opt_eng = qd['options_english']
                            opt_hin = qd['options_hindi']
                            opt_eng_list = [opt_eng.get(k, "") for k in ['a','b','c','d']]
                            opt_hin_list = [opt_hin.get(k, "") for k in ['a','b','c','d']]
                            
                            is_selected = qd['quality_pass_flag'] if qd['quality_pass_flag'] is not None else False
                            # Infer rejection if not selected and feedback exists? or default False
                            # If flag is True -> Selected. If False -> Rejected. If None -> Pending.
                            # DB has BOOLEAN.
                            is_rejected = not is_selected if qd['quality_pass_flag'] is not None else False
                            
                            q_obj = Question(
                                id=qd['question_number'], 
                                db_uuid=str(qd['id']),
                                question_number=qd['question_number'],
                                question_english=qd['question_english'],
                                options_english=opt_eng_list,
                                question_hindi=qd['question_hindi'],
                                options_hindi=opt_hin_list,
                                answer=qd['answer'],
                                question_blueprint=qd['question_blueprint'],
                                subject=qd['subject'],
                                user_feedback=qd['quality_feedback'],
                                is_selected=is_selected,
                                is_rejected=is_rejected
                            )
                            loaded_qs.append(q_obj)
                        except Exception as e:
                            print(f"Parse error: {e}")
                    
                    st.session_state.loaded_questions = loaded_qs
                    st.session_state.current_test_code = selected_code

                # Render Shared Review Interface
                if st.session_state.get('loaded_questions'):
                    render_review_interface(st.session_state.loaded_questions, st.session_state.current_test_code, 'loaded_questions')

elif mode == "Random Generation":
    st.header("Random Question Generation")

    # Pattern and Cognitive options with Randomize
    RANDOMIZE_OPTION = "🎲 Randomize"
    pattern_options = [
        RANDOMIZE_OPTION,
        "Standard Single-Correct",
        "Standard Single-Incorrect",
        "Multiple-Statement-2 (Correct)",
        "Multiple-Statement-3 (Correct)",
        "Multiple-Statement-4 (Correct)",
        "Multiple-Statement-2 (Incorrect)",
        "Multiple-Statement-3 (Incorrect)",
        "Multiple-Statement-4 (Incorrect)",
        "How Many - Statement",
        "How Many Pairs Correct/Incorrect",
        "How Many Sets/Triplets",
        "Std 2-Stmt Assertion-Reason",
        "Complex 3-Stmt Assertion-Reason",
        "Chronological Ordering",
        "Geographical Sequencing"
    ]
    cognitive_options = [
        RANDOMIZE_OPTION,
        "Recall/Recognition",
        "Comprehension/Conceptual",
        "Application/Analysis",
        "Higher Reasoning/Synthesis"
    ]
    difficulty_options = [RANDOMIZE_OPTION, "Easy", "Moderate", "Difficult"]

    col1, col2, col3 = st.columns([1, 1, 1.5])

    with col1:
        num_q_input = st.number_input("Number of Questions", 1, 50, 5)
        topic_input = st.text_input("Topic / Subject")

    with col2:
        main_pattern = st.selectbox("Question Pattern", options=pattern_options, index=0)
        main_cognitive = st.selectbox("Cognitive Level", options=cognitive_options, index=0)
        main_difficulty = st.selectbox("Difficulty", options=difficulty_options, index=0)

    with col3:
        source_text = st.text_area("Context / Text (Optional)", height=68)
        uploaded_pdf = st.file_uploader("Upload PDF (Optional)", type=['pdf'])

    # Advanced configuration (collapsed by default)
    # Initialize session state for tracking if user enabled advanced config
    if 'use_advanced_config' not in st.session_state:
        st.session_state.use_advanced_config = False

    config_list = []
    table_sum = 0

    use_advanced = st.checkbox("⚙️ Use Advanced Configuration", value=st.session_state.use_advanced_config, key="adv_config_checkbox")
    st.session_state.use_advanced_config = use_advanced

    # Show which input method is being used
    if use_advanced:
        st.info("📋 **Using Configuration Table** - Questions will be generated from the table rows below")
    else:
        st.info("📝 **Using Main Input Boxes** - Questions will be generated from the input fields above")

    if use_advanced:
        with st.container(border=True):
            config_list = get_config_table("random")
            table_sum = sum(item['count'] for item in config_list) if config_list else 0

    # Only use table sum if advanced config is enabled, otherwise use top input
    num_q = table_sum if use_advanced and table_sum > 0 else num_q_input

    # Show configuration preview when not using advanced config
    if not use_advanced and num_q_input > 0:
        with st.expander("📋 Preview Distribution", expanded=False):
            # Add a shuffle button to regenerate the preview
            col_preview_left, col_preview_right = st.columns([3, 1])
            with col_preview_right:
                if st.button("🔀 Shuffle Preview", key="shuffle_preview_simple"):
                    # Force regeneration by incrementing a counter
                    if 'preview_shuffle_count' not in st.session_state:
                        st.session_state.preview_shuffle_count = 0
                    st.session_state.preview_shuffle_count += 1
                    st.rerun()

            # Generate preview using the same logic as auto_distribute_empty_fields
            # Create a config item that mimics what will be sent to generation
            preview_config = [{
                'topic': topic_input if topic_input and topic_input.strip() else '',
                'pattern': None if main_pattern == RANDOMIZE_OPTION else main_pattern,
                'cognitive': None if main_cognitive == RANDOMIZE_OPTION else main_cognitive,
                'difficulty': None if main_difficulty == RANDOMIZE_OPTION else main_difficulty,
                'count': num_q_input,
                '_randomize_topic': not topic_input or not topic_input.strip(),
                '_randomize_pattern': main_pattern == RANDOMIZE_OPTION,
                '_randomize_cognitive': main_cognitive == RANDOMIZE_OPTION,
                '_randomize_difficulty': main_difficulty == RANDOMIZE_OPTION
            }]

            # Use auto_distribute_empty_fields to get the actual distribution
            expanded_config = auto_distribute_empty_fields(preview_config)

            # Shuffle the order to show questions in random order
            random.shuffle(expanded_config)

            # Generate preview data from expanded config
            preview_data = []
            for i, item in enumerate(expanded_config):
                preview_data.append({
                    "#": i + 1,
                    "Topic": item['topic'] if item['topic'] else "🎲",
                    "Pattern": item['pattern'],
                    "Cognitive": item['cognitive'],
                    "Difficulty": item['difficulty']
                })

            st.dataframe(pd.DataFrame(preview_data), width="stretch", hide_index=True)

            # Show randomization info
            randomized = []
            if main_pattern == RANDOMIZE_OPTION:
                randomized.append("Pattern")
            if main_cognitive == RANDOMIZE_OPTION:
                randomized.append("Cognitive")
            if main_difficulty == RANDOMIZE_OPTION:
                randomized.append("Difficulty")
            if not topic_input or not topic_input.strip():
                randomized.append("Topic")
            if randomized:
                st.info(f"🎲 Auto-distributing: {', '.join(randomized)}")

    st.metric("Total Questions to Generate", num_q)

    if st.button("🚀 Generate", type="primary"):
        if num_q == 0:
            st.error("Please add at least one row with Count > 0 in the configuration table.")
        else:
            # Validate Topic Source
            has_context = bool((source_text and source_text.strip()) or uploaded_pdf)
            has_main_topic = bool(topic_input and topic_input.strip())

            rows_have_topics = True
            if config_list:
                for item in config_list:
                    if not item.get('topic') or not item['topic'].strip():
                        rows_have_topics = False
                        break

            # Validation Logic
            if not config_list and not (has_context or has_main_topic):
                st.error("Please provide a Topic/Context or add rows to the configuration.")
            elif config_list and not (has_context or has_main_topic or rows_have_topics):
                st.error("Missing Topic Source! Please provide either:\n1. A Context (Text/PDF)\n2. A Main Topic/Subject\n3. Specific Topics for EVERY row in the configuration table.")
            else:
                # Prepare Final Config
                final_config = []

                # Process Table Rows
                for item in config_list:
                    # If row topic is missing, use main topic if available.
                    if (not item['topic'] or not item['topic'].strip()) and has_main_topic:
                        item['topic'] = topic_input
                    final_config.append(item)

                # If config is completely empty (no rows), create one full row using main inputs
                if not final_config and num_q > 0:
                    rem_topic = topic_input if has_main_topic else ""
                    # Check if main fields are randomized
                    pattern_val = None if main_pattern == RANDOMIZE_OPTION else main_pattern
                    cognitive_val = None if main_cognitive == RANDOMIZE_OPTION else main_cognitive
                    difficulty_val = None if main_difficulty == RANDOMIZE_OPTION else main_difficulty

                    final_config.append({
                        "topic": rem_topic,
                        "pattern": pattern_val,
                        "cognitive": cognitive_val,
                        "difficulty": difficulty_val,
                        "count": num_q,
                        "_randomize_topic": not has_main_topic,
                        "_randomize_pattern": main_pattern == RANDOMIZE_OPTION,
                        "_randomize_cognitive": main_cognitive == RANDOMIZE_OPTION,
                        "_randomize_difficulty": main_difficulty == RANDOMIZE_OPTION
                    })

            with st.status("Generating...", expanded=True) as status:
                try:
                    questions_obj, usage = asyncio.run(manager.generate_questions(
                        source_text=source_text,
                        uploaded_pdf=uploaded_pdf,
                        topic_input=topic_input, # Passed for context planning
                        question_distribution=final_config
                    ))
                    st.session_state.random_questions = questions_obj.questions
                    status.update(label="Done!", state="complete")
                except Exception as e:
                    st.error(f"Error: {e}")

    # Results for Random
    if 'random_questions' in st.session_state:
        qs = st.session_state.random_questions
        st.divider()
        st.subheader("Results")
        
        # We use a dummy test code for docx download
        render_review_interface(qs, "random_generated", 'random_questions')
keep_alive_heartbeat()