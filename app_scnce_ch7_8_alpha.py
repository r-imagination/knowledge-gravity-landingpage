import json
import os
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import google.generativeai as genai

# ==================================================
# Gemini setup
# ==================================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

def safe_generate(prompt: str) -> str:
    try:
        resp = gemini_model.generate_content(prompt)
        if hasattr(resp, "text") and resp.text:
            return resp.text.strip()[:1500]
        return "⚠️ Gemini returned no text."
    except Exception as e:
        return f"❌ Gemini error: {e}"

def build_context(concept, activities, grade):
    ctx = f"""
You are an expert teacher of Indian school curriculum interacting with students of age 10 years to 12 years.

Grade: {grade}
Concept: {concept['concept_name']}

Explanation:
{concept.get('brief_explanation', '')}

Concept Type: {concept.get('concept_type', '')}
Cognitive Level: {concept.get('cognitive_level', '')}

Chapters:
{", ".join(concept.get('chapter_references', []))}
"""
    if activities:
        ctx += "\nLearning Activities:\n"
        for a in activities:
            ctx += f"- {a['activity_name']}: {a['learning_goal']}\n"
    return ctx.strip()

def gemini_explain(context):
    prompt = f"""{context}

Task:
-Explain this concept clearly in simple language with a real-life example.
-If learning activities are provided, explain how doing those activities helps understanding.
-Give a cue for driving curiosity about the concept
-Limit to about 100-150 words.
CONTEXT:
{context}
"""
  
    return safe_generate(prompt)

def gemini_quiz(context):
    prompt = f"""{context}

Task:
Assume students are somewhat familiar with the concept, give a cue about it in one sentence. Create 3 questions:
1. Easy (recall)
2. Medium (understanding)
3. Application-based
Do NOT provide answers.
"""
    return safe_generate(prompt)

# ==================================================
# Streamlit config
# ==================================================
st.set_page_config(
    page_title="NCERT Knowledge Graph (Grades 7–8)",
    layout="wide"
)

DOMAIN_COLORS = {
    "Physics (The Physical World)": "#1f77b4",
    "Chemistry (The World of Matter)": "#2ca02c",
    "Biology (The Living World)": "#ff7f0e",
    "Earth & Space Science": "#9467bd",
    "Scientific Inquiry & Investigative Process": "#7f7f7f"
}

LEARNED_FILE = "learned_concepts.json"

# ==================================================
# Persistence
# ==================================================
def load_learned():
    if os.path.exists(LEARNED_FILE):
        with open(LEARNED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_learned(data):
    with open(LEARNED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ==================================================
# Load curriculum
# ==================================================
@st.cache_data
def load_all():
    with open("data/grade7_knowledge_base.json", "r", encoding="utf-8") as f:
        g7 = json.load(f)
    with open("data/grade8_knowledge_base.json", "r", encoding="utf-8") as f:
        g8 = json.load(f)
    return {"7": g7, "8": g8}

ALL_DATA = load_all()

# ==================================================
# Sidebar — Grade
# ==================================================
st.sidebar.markdown("## 📘 Curriculum")
grade = st.sidebar.radio("Select Grade", ["7", "8"], horizontal=True)

data = ALL_DATA[grade]
concepts = data["concepts"]
activities = data["activities"]

concept_map = {c["concept_name"]: c for c in concepts}
concept_names = set(concept_map.keys())

learned_store = load_learned()
learned_store.setdefault(grade, {})

# ==================================================
# Session state
# ==================================================
if "selected_concept" not in st.session_state:
    st.session_state.selected_concept = None
elif st.session_state.selected_concept not in concept_names:
    st.session_state.selected_concept = None

# ==================================================
# Build hierarchy
# ==================================================
domains = {}
strands = {}

for c in concepts:
    domains.setdefault(c["domain"], set()).add(c["strand"])
    strands.setdefault((c["domain"], c["strand"]), []).append(c["concept_name"])

concepts_with_acts = {a["parent_concept"] for a in activities if a.get("parent_concept")}

# ==================================================
# Nodes
# ==================================================
nodes = []

for domain in domains:
    nodes.append(Node(
        id=f"domain::{domain}",
        label=domain,
        shape="box",
        size=45,
        color=DOMAIN_COLORS.get(domain),
        font={"size": 18, "color": "white", "bold": True}
    ))

for (domain, strand) in strands:
    nodes.append(Node(
        id=f"strand::{strand}",
        label=strand,
        shape="ellipse",
        size=28,
        color=DOMAIN_COLORS.get(domain),
        font={"size": 14}
    ))

for c in concepts:
    has_activity = c["concept_name"] in concepts_with_acts
    nodes.append(Node(
        id=f"concept::{c['concept_name']}",
        label=c["concept_name"],
        shape="dot",
        size=18,
        color=DOMAIN_COLORS.get(c["domain"]),
        borderWidth=3 if has_activity else 1,
        borderColor="#111827",
        font={"size": 12}
    ))

# ==================================================
# Edges
# ==================================================
edges = []

for domain, strand_set in domains.items():
    for strand in strand_set:
        edges.append(Edge(
            source=f"domain::{domain}",
            target=f"strand::{strand}",
            color="#cccccc"
        ))

for (domain, strand), clist in strands.items():
    for c in clist:
        edges.append(Edge(
            source=f"strand::{strand}",
            target=f"concept::{c}",
            color="#dddddd"
        ))

for c in concepts:
    for linked in c.get("interconnections", []):
        if linked in concept_names:
            edges.append(Edge(
                source=f"concept::{c['concept_name']}",
                target=f"concept::{linked}",
                color="#ff9999"
            ))

# ==================================================
# Graph
# ==================================================
config = Config(
    width="100%",
    height=800,
    directed=False,
    physics=True,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    physics_config={
        "forceAtlas2Based": {
            "gravitationalConstant": -150,
            "springLength": 180,
            "avoidOverlap": 2.0
        }
    }
)

st.title(f"📘 NCERT Knowledge Graph — Grade {grade}")
selected = agraph(nodes=nodes, edges=edges, config=config)

clicked = None
if isinstance(selected, dict) and selected.get("nodes"):
    clicked = selected["nodes"][0]
elif isinstance(selected, list) and selected:
    clicked = selected[0]
elif isinstance(selected, str):
    clicked = selected

if isinstance(clicked, str) and clicked.startswith("concept::"):
    st.session_state.selected_concept = clicked.replace("concept::", "")

# ==================================================
# Define selected_concept
# ==================================================

selected_concept = None

if "selected_concept" in st.session_state:
    name = st.session_state.selected_concept
    if name and name in concept_map:
        selected_concept = concept_map[name]

# ==================================================
# Sidebar — Concept + Activities
# ==================================================
if selected_concept:
    st.sidebar.markdown(f"### {selected_concept['concept_name']}")

    with st.sidebar.expander("📘 Concept Info"):
        st.write(selected_concept["brief_explanation"])

        st.write("**Chapter(s):**")
        for ch in selected_concept["chapter_references"]:
            st.markdown(f"- {ch}")

        st.write("**Concept Type:**", selected_concept["concept_type"])
        st.write("**Cognitive Level:**", selected_concept["cognitive_level"])

    linked_acts = [a for a in activities if a.get("parent_concept") == concept["concept_name"]]

    with st.sidebar.expander(f"🧪 Activities ({len(linked_acts)})"):
        if linked_acts:
            for a in linked_acts:
                st.markdown(f"**{a['activity_name']}**")
                st.write(a["learning_goal"])
                st.markdown("---")
        else:
            st.write("No activities linked.")

    domain = concept["domain"]
    learned_store[grade].setdefault(domain, [])
    learned = concept["concept_name"] in learned_store[grade][domain]

    mark = st.sidebar.checkbox("✅ Mark concept as learned", value=learned)
    if mark and not learned:
        learned_store[grade][domain].append(concept["concept_name"])
        save_learned(learned_store)
    if not mark and learned:
        learned_store[grade][domain].remove(concept["concept_name"])
        save_learned(learned_store)

# ==================================================
# Sidebar — AI Tutor (FINAL)
# ==================================================
st.sidebar.divider()
st.sidebar.subheader("🤖 AI Learning Assistant")

if st.session_state.selected_concept:
    mode = st.sidebar.radio("Choose mode", ["Explain", "Quiz me"])

    if st.sidebar.button("Ask Gemini"):
        with st.spinner("Thinking..."):
            concept = concept_map[st.session_state.selected_concept]
            linked_acts = [a for a in activities if a.get("parent_concept") == concept["concept_name"]]
            context = build_context(concept, linked_acts, grade)

            if mode == "Explain":
                answer = gemini_explain(context)
            else:
                answer = gemini_quiz(context)

        st.sidebar.markdown("### 🤖 Gemini says")
        st.sidebar.write(answer)
else:
    st.sidebar.info("Select a concept to use AI assistance.")






