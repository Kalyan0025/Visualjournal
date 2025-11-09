import os
import io
import json
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------
# Utility: LLM call
# ---------------------------
def generate_paperscript(prompt: str) -> str:
    """
    Call Gemini to generate PaperScript (Paper.js) code.

    The model must return ONLY JavaScript/PaperScript code,
    no markdown, no explanation.
    """
    if not GEMINI_API_KEY:
        # Fallback: a tiny static demo if no API key
        return DEFAULT_FALLBACK_PAPERSCRIPT

    model = genai.GenerativeModel("gemini-1.5-pro")  # adjust if needed
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.9}
    )
    # Depending on SDK version, .text or .candidates[0].content.parts...
    try:
        return response.text
    except AttributeError:
        # Very rough fallback
        return str(response)

# ---------------------------
# Paper.js HTML wrapper
# ---------------------------
def build_paper_html(paperscript_code: str, canvas_id: str = "dreamCanvas") -> str:
    """
    Wrap generated PaperScript into a minimal HTML page
    that Streamlit can render via components.html.
    """
    # IMPORTANT: no backticks or <script> nesting issues.
    html = f"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/paper.js/0.12.15/paper-full.min.js"></script>
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: #111;
      }}
      canvas {{
        width: 100%;
        height: 100%;
      }}
      #container {{
        width: 100%;
        height: 100vh;
      }}
    </style>
  </head>
  <body>
    <div id="container">
      <canvas id="{canvas_id}" resize></canvas>
    </div>
    <script type="text/paperscript" canvas="{canvas_id}">
{paperscript_code}
    </script>
  </body>
</html>
    """
    return html

# ---------------------------
# Helpers: build prompts
# ---------------------------
def build_journal_prompt(user_text: str, context_type: str) -> str:
    """
    Create an instruction prompt for Gemini that describes
    how to turn free-text into a context-specific dream/memory doodle.
    """
    return f"""
You are a creative code generator that ONLY outputs PaperScript code
for the Paper.js library (no HTML, no markdown, no explanations).

Goal:
- Turn the following {context_type} journal text into a hand-drawn-style,
  animated visualization, in the spirit of Giorgia Lupi / Data Humanism.

Requirements:
- Use an off-white paper-like background or a context-appropriate background
  (for example, deep night blue for night oceans).
- Use wobbly, imperfect lines and circles by jittering points, as if drawn by hand.
- Use soft, semi-transparent colors with an ink/watercolor vibe.
- Add gentle, meaningful motion via onFrame(event):
  - calm scenes: slow floating or breathing motion
  - intense scenes: more pronounced, but still organic motion

Story context:
\"\"\"{user_text}\"\"\"


Visual design rules:
- Do NOT draw a calendar grid here unless the text clearly describes schedule-like data.
- Instead, choose a metaphor that fits the story:
  - If the story is about a dream of swimming across seas at night, use curves of the earth,
    waves, stars, and two swimmers.
  - If it is about a warm memory at a café, use circular tables, warm light halos, etc.
- Place any textual annotations as PointText in a subtle way (small caption or title).
- The drawing must fill a reasonably large canvas, for example about 1000x650.
  You can set it using:
    view.viewSize = new Size(1000, 650);

PaperScript constraints:
- Assume Paper.js is already imported.
- Do not include HTML or <script> tags.
- Start directly with PaperScript (JavaScript-like) code.
- Define an onFrame(event) handler if you want animation.

Output:
- ONLY valid PaperScript code.
    """

def summarize_dataframe(df: pd.DataFrame, max_rows: int = 5) -> str:
    """
    Turn a DataFrame into a text summary for the model.
    """
    buf = io.StringIO()
    buf.write("Columns:\n")
    buf.write(", ".join([f"{col} ({str(df[col].dtype)})" for col in df.columns]))
    buf.write("\n\nExample rows:\n")
    buf.write(df.head(max_rows).to_csv(index=False))
    buf.write("\n\nBasic stats (where numeric):\n")
    buf.write(df.describe(include="all", datetime_is_numeric=True).to_csv())
    return buf.getvalue()

def build_table_prompt(df: pd.DataFrame) -> str:
    summary = summarize_dataframe(df)
    return f"""
You are a creative code generator that ONLY outputs PaperScript code
for the Paper.js library (no HTML, no markdown, no explanations).

Goal:
- Turn the following tabular dataset into a human, hand-drawn-style
  grid or table visualization (Data Humanism style), similar to a calendar
  or matrix but with doodles representing the data in each cell.

Dataset summary:
----------------
{summary}
----------------

Visual design rules:
- Use an off-white paper-like background.
- Draw a grid or table that reflects the logical structure of the data:
  - rows = records, days, items
  - columns = features / categories
- Use wobbly sketch lines instead of perfectly straight grid lines
  (jitter the points on each line).
- For each row/column cell, draw a small doodle that reflects:
  - magnitude (size / length)
  - category (color or shape)
  - special values (e.g. missing, zero, high) with distinct marks.
- Avoid standard bar chart / pie chart style; think hand-drawn calendar
  or Dear Data postcard style.
- Include a title and a small legend using PointText and a small
  legend box in a corner.
- Canvas can be about 1100x700:
    view.viewSize = new Size(1100, 700);

PaperScript constraints:
- Assume Paper.js is already imported.
- Do not include HTML or <script> tags.
- Start directly with PaperScript code.
- Define an onFrame(event) ONLY if it helps with subtle motion (e.g. breathing).

Output:
- ONLY valid PaperScript code.
    """

# ---------------------------
# Fallback PaperScript (no API)
# ---------------------------
DEFAULT_FALLBACK_PAPERSCRIPT = """
// Fallback PaperScript demo (no API key found)
// Simple hand-drawn circle in a night sky.

var W = 900, H = 600;
view.viewSize = new Size(W, H);

var bg = new Path.Rectangle(view.bounds);
bg.fillColor = '#050b1a';

function j(a){ return (Math.random()-0.5)*a; }

function handCircle(center, radius, strokeCol, fillCol){
    var s = 40;
    var p = new Path();
    for (var i=0;i<s;i++){
        var ang = 360/s * i;
        var r = radius + j(radius*0.3);
        p.add(center.add(new Point({length:r, angle:ang})));
    }
    p.closed = true;
    p.strokeColor = strokeCol || new Color(1,1,1,0.9);
    p.strokeWidth = 1.4;
    if (fillCol) p.fillColor = fillCol;
    return p;
}

var center = new Point(W/2, H/2);
var moon = handCircle(center, 80,
                      new Color(1,1,1,0.9),
                      new Color(0.98,0.98,0.94, 0.95));

var title = new PointText({
    point: new Point(40, 40),
    content: "Fallback Visual · Add GEMINI_API_KEY to get custom doodles",
    justification: 'left',
    fillColor: new Color(1,1,1,0.85),
    fontFamily: 'Helvetica',
    fontSize: 16
});

var t = 0;
function onFrame(event){
    t += event.delta;
    moon.scale(1 + Math.sin(t*0.8)*0.0015);
    moon.fillColor.hue += 0.1;
}
"""

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Virtual Journal · Data Humanism", layout="wide")

st.title("📝 Virtual Journal · Data Humanism Visualiser")
st.caption("Write a dream or upload data — see a hand-drawn, living visual in Paper.js")

mode = st.sidebar.radio(
    "Choose mode",
    ["Journal / Dream Text", "Spreadsheet / Tabular Data"],
)

if not GEMINI_API_KEY:
    st.sidebar.warning("No GEMINI_API_KEY found – using fallback static demo.")

# Shared container for visualization
vis_container = st.empty()

if mode == "Journal / Dream Text":
    st.subheader("Journal / Dream Input")
    context_type = st.selectbox(
        "What kind of entry is this?",
        ["dream", "memory", "routine / day", "random thought"],
        index=0
    )
    user_text = st.text_area(
        "Write your entry here:",
        height=200,
        placeholder="Example: I was swimming across the seas all over the globe with Gomma at night..."
    )

    if st.button("Generate Visual", type="primary"):
        if not user_text.strip():
            st.error("Please write something first.")
        else:
            with st.spinner("Asking the doodle engine..."):
                prompt = build_journal_prompt(user_text, context_type)
                paperscript = generate_paperscript(prompt)

            st.subheader("Generated PaperScript (for debugging / curiosity)")
            with st.expander("Show code"):
                st.code(paperscript, language="javascript")

            html = build_paper_html(paperscript)
            components.html(html, height=720, scrolling=False)

else:
    st.subheader("Spreadsheet / Tabular Data Input")
    uploaded = st.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xlsx", "xls"]
    )

    if uploaded is not None:
        # Try to read into DataFrame
        try:
            if uploaded.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Error reading file: {e}")
            df = None

        if df is not None:
            st.write("Preview of your data:")
            st.dataframe(df.head())

            if st.button("Generate Grid Visual", type="primary"):
                with st.spinner("Translating your table into a humanistic grid..."):
                    prompt = build_table_prompt(df)
                    paperscript = generate_paperscript(prompt)

                st.subheader("Generated PaperScript (for debugging / curiosity)")
                with st.expander("Show code"):
                    st.code(paperscript, language="javascript")

                html = build_paper_html(paperscript)
                components.html(html, height=720, scrolling=False)
    else:
        st.info("Upload a CSV or Excel file to begin.")

st.markdown(
    """
---

_This version is ephemeral: nothing is stored.  
Each visual is a momentary mirror of your text or data._
"""
)
