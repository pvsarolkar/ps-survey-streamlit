import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import json
from datetime import datetime
import io
from typing import Dict, List, Any

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Partner Survey System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS - BROADCOM INSPIRED STYLING
# ============================================================================
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #0066CC 0%, #004499 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .stButton>button {
        background-color: #0066CC;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #004499;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .section-header {
        background-color: #f1f5f9;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        font-weight: 600;
        color: #0066CC;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================
@st.cache_resource
def get_db_connection():
    """Create and cache database connection"""
    try:
        # Read secrets with proper fallback
        db_host = st.secrets.get("DB_HOST") if "DB_HOST" in st.secrets else "localhost"
        db_port = st.secrets.get("DB_PORT") if "DB_PORT" in st.secrets else 5432
        db_name = st.secrets.get("DB_NAME") if "DB_NAME" in st.secrets else "postgres"
        db_user = st.secrets.get("DB_USER") if "DB_USER" in st.secrets else "postgres"
        db_password = st.secrets.get("DB_PASSWORD") if "DB_PASSWORD" in st.secrets else ""
        
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        # Show debug info
        if "DB_HOST" in st.secrets:
            st.info(f"Attempting to connect to: {st.secrets['DB_HOST']}:{st.secrets.get('DB_PORT', 5432)}")
        else:
            st.warning("⚠️ Database credentials not found in secrets. Please configure them in Settings → Secrets")
        return None

def execute_query(query: str, params: tuple = None, fetch: bool = True):
    """Execute database query with error handling"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
                return result
            else:
                conn.commit()
                return True
    except Exception as e:
        conn.rollback()
        st.error(f"Database error: {str(e)}")
        return None

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_all_surveys():
    """Fetch all available surveys"""
    query = """
        SELECT 
            template_name as survey_name,
            description,
            questions,
            created_date,
            updated_date
        FROM templates 
        ORDER BY created_date DESC
    """
    return execute_query(query)

def get_customers(search_term: str = ""):
    """Search customers by company name or ID"""
    if search_term:
        query = """
            SELECT customer_id, customer_company, classification, owner
            FROM customers 
            WHERE customer_company ILIKE %s OR customer_id ILIKE %s
            ORDER BY customer_company ASC
            LIMIT 50
        """
        return execute_query(query, (f"%{search_term}%", f"%{search_term}%"))
    else:
        query = """
            SELECT customer_id, customer_company, classification, owner
            FROM customers 
            ORDER BY customer_company ASC
            LIMIT 50
        """
        return execute_query(query)

def check_existing_responses(customer_id: str, partner_company: str, template_name: str):
    """Check if responses already exist for this combination"""
    query = """
        SELECT 
            r.question_id, 
            r.response_value, 
            s.submission_date,
            p.partner_name as previous_partner_name,
            c.customer_company
        FROM responses r
        JOIN submissions s ON r.submission_id = s.id
        JOIN partners p ON s.partner_id = p.id
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN templates t ON s.template_id = t.id
        WHERE s.customer_id = %s 
        AND p.partner_company = %s 
        AND t.template_name = %s
        AND s.id = (
            SELECT MAX(s2.id) 
            FROM submissions s2 
            JOIN partners p2 ON s2.partner_id = p2.id
            JOIN templates t2 ON s2.template_id = t2.id
            WHERE s2.customer_id = %s
            AND p2.partner_company = %s
            AND t2.template_name = %s
        )
    """
    results = execute_query(query, (customer_id, partner_company, template_name, 
                                    customer_id, partner_company, template_name))
    
    if results and len(results) > 0:
        responses = {row['question_id']: row['response_value'] for row in results}
        return {
            'has_existing': True,
            'responses': responses,
            'submission_date': results[0]['submission_date'],
            'previous_partner_name': results[0]['previous_partner_name'],
            'customer_company': results[0]['customer_company']
        }
    return {'has_existing': False}

def submit_survey_responses(customer_id: str, customer_company: str, 
                           partner_name: str, partner_company: str,
                           template_name: str, responses: Dict, is_update: bool = False):
    """Submit survey responses to database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Insert or get customer
            cur.execute("""
                INSERT INTO customers (customer_id, customer_company) 
                VALUES (%s, %s) 
                ON CONFLICT (customer_id) DO UPDATE SET customer_company = %s 
                RETURNING customer_id
            """, (customer_id, customer_company, customer_company))
            
            # Insert or get partner
            cur.execute("""
                INSERT INTO partners (partner_name, partner_company) 
                VALUES (%s, %s) 
                ON CONFLICT (partner_name, partner_company) DO UPDATE SET partner_name = %s 
                RETURNING id
            """, (partner_name, partner_company, partner_name))
            partner_id = cur.fetchone()[0]
            
            # Get template ID
            cur.execute("""
                SELECT id, questions FROM templates WHERE template_name = %s
            """, (template_name,))
            template_result = cur.fetchone()
            if not template_result:
                raise Exception(f"Template '{template_name}' not found")
            template_id = template_result[0]
            template_questions = template_result[1]
            
            # Get previous submission ID if updating
            previous_submission_id = None
            if is_update:
                cur.execute("""
                    SELECT MAX(s.id) as id
                    FROM submissions s
                    JOIN partners p ON s.partner_id = p.id
                    WHERE s.customer_id = %s 
                    AND p.partner_name = %s 
                    AND p.partner_company = %s 
                    AND s.template_id = %s
                """, (customer_id, partner_name, partner_company, template_id))
                prev_result = cur.fetchone()
                if prev_result and prev_result[0]:
                    previous_submission_id = prev_result[0]
            
            # Create new submission
            cur.execute("""
                INSERT INTO submissions (customer_id, partner_id, template_id, is_update, previous_submission_id) 
                VALUES (%s, %s, %s, %s, %s) 
                RETURNING id, submission_uuid
            """, (customer_id, partner_id, template_id, is_update, previous_submission_id))
            submission_result = cur.fetchone()
            submission_id = submission_result[0]
            submission_uuid = submission_result[1]
            
            # Insert responses
            for question_id, response_value in responses.items():
                if response_value is not None and response_value != '':
                    # Find question details from template
                    question_detail = next((q for q in template_questions if q['id'] == question_id), None)
                    question_text = question_detail['question'] if question_detail else question_id
                    response_type = question_detail['type'] if question_detail else 'unknown'
                    section_name = question_detail.get('section') if question_detail else None
                    
                    cur.execute("""
                        INSERT INTO responses (submission_id, question_id, question_text, response_value, response_type, section_name) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (submission_id, question_id, question_text, str(response_value), response_type, section_name))
            
            conn.commit()
            return {'success': True, 'submission_id': submission_id, 'submission_uuid': str(submission_uuid)}
    
    except Exception as e:
        conn.rollback()
        st.error(f"Error submitting responses: {str(e)}")
        return {'success': False, 'error': str(e)}

def upload_template(survey_name: str, questions: List[Dict], description: str = ""):
    """Upload a new survey template"""
    query = """
        INSERT INTO templates (template_name, questions, description) 
        VALUES (%s, %s, %s) 
        ON CONFLICT (template_name) 
        DO UPDATE SET questions = %s, updated_date = CURRENT_TIMESTAMP
        RETURNING id
    """
    questions_json = json.dumps(questions)
    result = execute_query(query, (survey_name, questions_json, description, questions_json), fetch=True)
    return result is not None

def export_all_submissions():
    """Export all submissions to Excel"""
    query = """
        SELECT 
            s.submission_uuid,
            s.submission_date,
            s.customer_id,
            c.customer_company,
            p.partner_name,
            p.partner_company,
            t.template_name as survey_name,
            s.is_update,
            r.question_id,
            r.question_text,
            r.response_value,
            r.response_type,
            r.section_name
        FROM submissions s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN partners p ON s.partner_id = p.id
        JOIN templates t ON s.template_id = t.id
        LEFT JOIN responses r ON s.id = r.submission_id
        ORDER BY s.submission_date DESC, r.question_id
    """
    results = execute_query(query)
    
    if not results:
        return None
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Create Excel file with multiple sheets
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        summary_df = df.groupby(['submission_uuid', 'submission_date', 'customer_id', 
                                 'customer_company', 'partner_name', 'partner_company', 
                                 'survey_name', 'is_update']).size().reset_index(name='response_count')
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Detailed responses sheet
        detailed_df = df[df['response_value'].notna()][['submission_uuid', 'submission_date', 
                                                          'customer_id', 'customer_company', 
                                                          'partner_name', 'partner_company', 
                                                          'survey_name', 'section_name', 
                                                          'question_id', 'question_text', 
                                                          'response_value', 'response_type']]
        detailed_df.to_excel(writer, sheet_name='Detailed Responses', index=False)
    
    output.seek(0)
    return output

# ============================================================================
# FILE PARSING UTILITIES
# ============================================================================

def parse_survey_file(uploaded_file):
    """Parse Excel or CSV file to extract survey questions"""
    try:
        # Read file based on extension
        if uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.xls'):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload .xlsx, .xls, or .csv file.")
            return None
        
        questions = []
        for idx, row in df.iterrows():
            question = {
                'id': row.get('QuestionID', f'Q{idx+1}'),
                'type': str(row.get('Type', 'text')).lower(),
                'question': str(row.get('Question', '')),
                'section': str(row.get('Section', '')),
                'required': str(row.get('Required', 'No')) in ['Yes', 'TRUE', 'True', 'yes', 'true']
            }
            
            # Handle question-specific fields
            if question['type'] in ['multiple_choice', 'multiple_choice_single_select', 'multiple_choice_multi_select']:
                options = row.get('Options', '')
                if pd.notna(options) and str(options).strip():
                    # Try different separators: comma, pipe, semicolon
                    options_str = str(options)
                    if '|' in options_str:
                        question['options'] = [opt.strip() for opt in options_str.split('|') if opt.strip()]
                    elif ';' in options_str:
                        question['options'] = [opt.strip() for opt in options_str.split(';') if opt.strip()]
                    else:
                        question['options'] = [opt.strip() for opt in options_str.split(',') if opt.strip()]
                else:
                    question['options'] = []
            
            elif question['type'] == 'rating':
                question['minRating'] = int(row.get('MinRating', 1))
                question['maxRating'] = int(row.get('MaxRating', 5))
            
            elif question['type'] == 'matrix':
                matrix_rows = row.get('MatrixRows', '')
                matrix_cols = row.get('MatrixCols', '')
                if pd.notna(matrix_rows) and str(matrix_rows).strip():
                    rows_str = str(matrix_rows)
                    if '|' in rows_str:
                        question['matrixRows'] = [r.strip() for r in rows_str.split('|') if r.strip()]
                    else:
                        question['matrixRows'] = [r.strip() for r in rows_str.split(',') if r.strip()]
                else:
                    question['matrixRows'] = []
                    
                if pd.notna(matrix_cols) and str(matrix_cols).strip():
                    cols_str = str(matrix_cols)
                    if '|' in cols_str:
                        question['matrixCols'] = [c.strip() for c in cols_str.split('|') if c.strip()]
                    else:
                        question['matrixCols'] = [c.strip() for c in cols_str.split(',') if c.strip()]
                else:
                    question['matrixCols'] = []
            
            # Handle dependencies
            if pd.notna(row.get('DependsOn')):
                question['dependsOn'] = str(row['DependsOn'])
                if pd.notna(row.get('DependsOnValue')):
                    question['dependsOnValue'] = str(row['DependsOnValue'])
            
            questions.append(question)
        
        return questions
    
    except Exception as e:
        st.error(f"Error parsing file: {str(e)}")
        return None

# ============================================================================
# SURVEY RENDERING COMPONENTS
# ============================================================================

def should_show_question(question: Dict, responses: Dict) -> bool:
    """Check if question should be shown based on dependencies"""
    if 'dependsOn' not in question:
        return True
    
    depends_on_id = question['dependsOn']
    depends_on_value = question.get('dependsOnValue')
    
    if depends_on_id not in responses:
        return False
    
    current_value = responses[depends_on_id]
    
    if depends_on_value:
        return str(current_value) == str(depends_on_value)
    else:
        return bool(current_value)

def render_question(question: Dict, key_prefix: str = ""):
    """Render a single question based on its type"""
    q_id = question['id']
    q_text = question['question']
    q_type = question['type']
    required = question.get('required', False)
    
    label = f"{q_text} {'*' if required else ''}"
    key = f"{key_prefix}_{q_id}"
    
    # Get existing value from session state
    existing_value = st.session_state.survey_responses.get(q_id, "")
    
    # Debug: Show question type and options (temporary)
    # st.caption(f"Debug - Type: {q_type}, Options: {question.get('options', 'N/A')}")
    
    if q_type == 'text':
        return st.text_input(label, value=existing_value, key=key)
    
    elif q_type == 'textarea':
        return st.text_area(label, value=existing_value, key=key, height=100)
    
    elif q_type == 'multiple_choice_single_select':
        options = question.get('options', [])
        index = options.index(existing_value) if existing_value in options else 0
        return st.selectbox(label, options=[""] + options, index=index if existing_value else 0, key=key)
    
    elif q_type == 'multiple_choice_multi_select':
        options = question.get('options', [])
        default = existing_value.split('|') if existing_value else []
        selected = st.multiselect(label, options=options, default=default, key=key)
        return '|'.join(selected) if selected else ""
    
    elif q_type == 'rating':
        min_rating = question.get('minRating', 1)
        max_rating = question.get('maxRating', 5)
        value = int(existing_value) if existing_value and str(existing_value).replace('-','').isdigit() else min_rating
        return st.slider(label, min_value=min_rating, max_value=max_rating, value=value, key=key)
    
    elif q_type == 'matrix':
        st.write(label)
        matrix_rows = question.get('matrixRows', [])
        matrix_cols = question.get('matrixCols', [])
        
        # Debug: Show if matrix data is missing
        if not matrix_rows or not matrix_cols:
            st.warning(f"⚠️ Matrix question missing data. Rows: {len(matrix_rows)}, Cols: {len(matrix_cols)}")
            st.caption(f"Debug - Rows: {matrix_rows}, Cols: {matrix_cols}")
            return ""
        
        # Load existing responses
        existing_matrix = {}
        if existing_value:
            try:
                existing_matrix = json.loads(existing_value)
            except:
                pass
        
        # Create matrix table using columns
        matrix_responses = {}
        
        # Create a container for better styling
        st.markdown("---")
        
        # Add custom CSS to hide radio button text and style the matrix
        st.markdown("""
        <style>
        /* Hide the radio button labels since we have headers */
        div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child {
            display: none !important;
        }
        /* Style the matrix container */
        .matrix-table-container {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            margin: 10px 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create a clean table structure
        st.markdown('<div class="matrix-table-container">', unsafe_allow_html=True)
        
        # Calculate column widths to match radio button spacing
        # First column for aspect names, rest divided equally for radio buttons
        num_options = len(matrix_cols)
        col_widths = [2] + [1] * num_options
        
        # Header row
        header_cols = st.columns(col_widths)
        with header_cols[0]:
            st.markdown('<div style="padding: 12px; font-weight: bold; background-color: #f8f9fa; border-bottom: 2px solid #d0d0d0;">Aspect</div>', unsafe_allow_html=True)
        
        for idx, col_name in enumerate(matrix_cols):
            with header_cols[idx + 1]:
                st.markdown(f'<div style="padding: 12px; font-weight: bold; background-color: #f8f9fa; border-bottom: 2px solid #d0d0d0; text-align: center;">{col_name}</div>', unsafe_allow_html=True)
        
        # Data rows with radio buttons
        for row_idx, row_name in enumerate(matrix_rows):
            # Get existing value for this row
            existing_row_value = existing_matrix.get(row_name, None)
            selected_idx = None
            if existing_row_value and existing_row_value in matrix_cols:
                selected_idx = matrix_cols.index(existing_row_value)
            
            # Create columns for this row
            row_cols = st.columns(col_widths)
            
            # Aspect name in first column
            with row_cols[0]:
                st.markdown(f'<div style="padding: 12px; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; min-height: 50px;">{row_name}</div>', unsafe_allow_html=True)
            
            # Create a unique key for this row's radio group
            row_key = f"{key}_{row_name.replace(' ', '_').replace('|', '_')}_{row_idx}"
            
            # Place each radio button in its corresponding column
            for col_idx, col_name in enumerate(matrix_cols):
                with row_cols[col_idx + 1]:
                    # Create a container with border
                    st.markdown(f'<div style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: center; min-height: 50px; display: flex; align-items: center; justify-content: center;">', unsafe_allow_html=True)
                    
                    # Single radio button for this cell
                    is_selected = (existing_row_value == col_name)
                    cell_key = f"{row_key}_{col_idx}"
                    
                    if st.radio(
                        label=col_name,
                        options=[col_name],
                        index=0 if is_selected else None,
                        key=cell_key,
                        label_visibility="collapsed"
                    ):
                        matrix_responses[row_name] = col_name
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        return json.dumps(matrix_responses) if matrix_responses else ""
    
    else:  # default to text
        return st.text_input(label, value=existing_value, key=key)

def render_survey_form(survey_config: Dict):
    """Render complete survey form"""
    questions = survey_config['questions']
    
    # Group questions by section
    sections = {}
    for q in questions:
        section = q.get('section', 'General')
        if section not in sections:
            sections[section] = []
        sections[section].append(q)
    
    # Render sections
    for section_name, section_questions in sections.items():
        st.markdown(f'<div class="section-header">📋 {section_name}</div>', unsafe_allow_html=True)
        
        for question in section_questions:
            if should_show_question(question, st.session_state.survey_responses):
                response = render_question(question, key_prefix=f"survey_{section_name}")
                st.session_state.survey_responses[question['id']] = response
    
    # Progress indicator
    total_questions = len([q for q in questions if should_show_question(q, st.session_state.survey_responses)])
    answered_questions = len([q for q in questions if should_show_question(q, st.session_state.survey_responses) 
                              and st.session_state.survey_responses.get(q['id'])])
    
    if total_questions > 0:
        progress = answered_questions / total_questions
        st.progress(progress)
        st.caption(f"Progress: {answered_questions}/{total_questions} questions answered ({int(progress*100)}%)")

# ============================================================================
# ADMIN MODE INTERFACE
# ============================================================================

def render_admin_mode():
    """Render admin interface"""
    st.header("🔧 Admin Mode")
    
    tab1, tab2, tab3 = st.tabs(["📤 Upload Survey Template", "📋 View Surveys", "📊 Export Data"])
    
    # Tab 1: Upload Template
    with tab1:
        st.subheader("Upload Survey Template")
        st.info("Upload Excel or CSV file with survey questions. Required columns: QuestionID, Type, Question, Section, Required")
        
        survey_name = st.text_input("Survey Name", placeholder="e.g., Partner Satisfaction Survey 2025")
        description = st.text_area("Description (optional)", placeholder="Brief description of this survey")
        
        uploaded_files = st.file_uploader(
            "Upload Template Files (Excel or CSV)", 
            type=['xlsx', 'xls', 'csv'],
            accept_multiple_files=True
        )
        
        if uploaded_files and survey_name:
            all_questions = []
            
            for uploaded_file in uploaded_files:
                st.write(f"📄 Processing: {uploaded_file.name}")
                questions = parse_survey_file(uploaded_file)
                if questions:
                    all_questions.extend(questions)
                    st.success(f"✅ Parsed {len(questions)} questions from {uploaded_file.name}")
            
            if all_questions:
                st.write(f"**Total Questions:** {len(all_questions)}")
                
                # Preview questions
                with st.expander("Preview Questions"):
                    preview_df = pd.DataFrame([{
                        'ID': q['id'],
                        'Type': q['type'],
                        'Question': q['question'][:50] + '...' if len(q['question']) > 50 else q['question'],
                        'Section': q.get('section', ''),
                        'Required': q.get('required', False)
                    } for q in all_questions])
                    st.dataframe(preview_df, use_container_width=True)
                
                if st.button("💾 Save Survey Template", type="primary"):
                    if upload_template(survey_name, all_questions, description):
                        st.success(f"✅ Survey '{survey_name}' saved successfully with {len(all_questions)} questions!")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save survey template")
    
    # Tab 2: View Surveys
    with tab2:
        st.subheader("Available Surveys")
        surveys = get_all_surveys()
        
        if surveys:
            for survey in surveys:
                with st.expander(f"📋 {survey['survey_name']} ({len(survey['questions'])} questions)"):
                    st.write(f"**Description:** {survey.get('description', 'N/A')}")
                    st.write(f"**Created:** {survey['created_date']}")
                    st.write(f"**Last Updated:** {survey['updated_date']}")
                    
                    # Show questions
                    questions_df = pd.DataFrame([{
                        'ID': q['id'],
                        'Type': q['type'],
                        'Question': q['question'],
                        'Section': q.get('section', ''),
                        'Required': q.get('required', False)
                    } for q in survey['questions']])
                    st.dataframe(questions_df, use_container_width=True)
        else:
            st.info("No surveys available. Upload a template to get started.")
    
    # Tab 3: Export Data
    with tab3:
        st.subheader("Export Survey Data")
        
        if st.button("📥 Export All Submissions to Excel", type="primary"):
            with st.spinner("Generating Excel file..."):
                excel_file = export_all_submissions()
                
                if excel_file:
                    st.download_button(
                        label="⬇️ Download Excel File",
                        data=excel_file,
                        file_name=f"All_Submissions_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("✅ Export ready for download!")
                else:
                    st.warning("No submissions found to export")

# ============================================================================
# PARTNER MODE INTERFACE
# ============================================================================

def render_partner_mode():
    """Render partner interface"""
    st.header("👥 Partner Mode")
    
    # Initialize session state
    if 'survey_responses' not in st.session_state:
        st.session_state.survey_responses = {}
    if 'selected_customer' not in st.session_state:
        st.session_state.selected_customer = None
    if 'selected_survey' not in st.session_state:
        st.session_state.selected_survey = None
    if 'existing_responses_checked' not in st.session_state:
        st.session_state.existing_responses_checked = False
    
    # Step 1: Partner Information
    st.subheader("1️⃣ Partner Information")
    col1, col2 = st.columns(2)
    with col1:
        partner_name = st.text_input("Partner User Name *", placeholder="Your name")
    with col2:
        partner_company = st.text_input("Partner Company *", placeholder="Your company name")
    
    # Step 2: Customer Selection
    st.subheader("2️⃣ Select Customer")
    search_term = st.text_input("🔍 Search Customer", placeholder="Search by company name or ID")
    
    customers = get_customers(search_term)
    if customers:
        customer_options = {f"{c['customer_company']} ({c['customer_id']})": c for c in customers}
        selected_customer_key = st.selectbox(
            "Select Customer",
            options=[""] + list(customer_options.keys())
        )
        
        if selected_customer_key:
            st.session_state.selected_customer = customer_options[selected_customer_key]
            customer = st.session_state.selected_customer
            
            # Display customer info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**ID:** {customer['customer_id']}")
            with col2:
                st.info(f"**Classification:** {customer.get('classification', 'N/A')}")
            with col3:
                st.info(f"**Owner:** {customer.get('owner', 'N/A')}")
    
    # Step 3: Survey Selection
    st.subheader("3️⃣ Select Survey")
    surveys = get_all_surveys()
    
    if surveys:
        survey_options = {s['survey_name']: s for s in surveys}
        selected_survey_name = st.selectbox(
            "Choose Survey",
            options=[""] + list(survey_options.keys())
        )
        
        if selected_survey_name:
            st.session_state.selected_survey = survey_options[selected_survey_name]
            survey = st.session_state.selected_survey
            st.info(f"📋 {survey.get('description', '')} ({len(survey['questions'])} questions)")
    
    # Step 4: Check for existing responses
    if (st.session_state.selected_customer and st.session_state.selected_survey and 
        partner_company and not st.session_state.existing_responses_checked):
        
        customer_id = st.session_state.selected_customer['customer_id']
        template_name = st.session_state.selected_survey['survey_name']
        
        existing_data = check_existing_responses(customer_id, partner_company, template_name)
        
        if existing_data['has_existing']:
            st.warning(f"""
                ⚠️ **Existing Response Found**
                
                A previous response was submitted on {existing_data['submission_date']} 
                by {existing_data['previous_partner_name']} from {partner_company}.
                
                You can review and update the responses below.
            """)
            st.session_state.survey_responses = existing_data['responses']
            st.session_state.is_update = True
        else:
            st.session_state.is_update = False
        
        st.session_state.existing_responses_checked = True
    
    # Step 5: Survey Form
    if st.session_state.selected_customer and st.session_state.selected_survey and partner_name and partner_company:
        st.markdown("---")
        st.subheader("4️⃣ Complete Survey")
        
        render_survey_form(st.session_state.selected_survey)
        
        # Submit button
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📤 Submit Survey", type="primary", use_container_width=True):
                # Validate required fields
                questions = st.session_state.selected_survey['questions']
                missing_required = []
                
                for q in questions:
                    if q.get('required') and should_show_question(q, st.session_state.survey_responses):
                        if not st.session_state.survey_responses.get(q['id']):
                            missing_required.append(q['question'])
                
                if missing_required:
                    st.error(f"❌ Please answer all required questions. Missing: {', '.join(missing_required[:3])}")
                else:
                    # Submit responses
                    result = submit_survey_responses(
                        customer_id=st.session_state.selected_customer['customer_id'],
                        customer_company=st.session_state.selected_customer['customer_company'],
                        partner_name=partner_name,
                        partner_company=partner_company,
                        template_name=st.session_state.selected_survey['survey_name'],
                        responses=st.session_state.survey_responses,
                        is_update=st.session_state.get('is_update', False)
                    )
                    
                    if result and result.get('success'):
                        st.success(f"""
                            ✅ **Survey Submitted Successfully!**
                            
                            Submission ID: {result['submission_uuid']}
                            
                            Thank you for completing the survey!
                        """)
                        st.balloons()
                        
                        # Reset form
                        if st.button("Start New Survey"):
                            st.session_state.survey_responses = {}
                            st.session_state.selected_customer = None
                            st.session_state.selected_survey = None
                            st.session_state.existing_responses_checked = False
                            st.rerun()
                    else:
                        st.error(f"❌ Failed to submit survey: {result.get('error', 'Unknown error')}")
    
    elif not (partner_name and partner_company):
        st.info("👆 Please enter your partner information to continue")
    elif not st.session_state.selected_customer:
        st.info("👆 Please select a customer to continue")
    elif not st.session_state.selected_survey:
        st.info("👆 Please select a survey to continue")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown("""
        <div class="main-header">
            <h1>📊 Partner Survey System</h1>
            <p>Streamlit Edition - Connected to PostgreSQL</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🔧 Navigation")
    
    # Connection status
    conn = get_db_connection()
    if conn:
        st.sidebar.success("✅ Database Connected")
    else:
        st.sidebar.error("❌ Database Connection Failed")
        st.error("Please configure database credentials in Streamlit secrets")
        return
    
    # Mode selection
    mode = st.sidebar.radio(
        "Select Mode:",
        ["👥 Partner Mode", "🔧 Admin Mode"],
        index=0
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("""
        **Partner Mode:** Fill out surveys for customers
        
        **Admin Mode:** Upload templates and export data
    """)
    
    # Render selected mode
    if mode == "🔧 Admin Mode":
        render_admin_mode()
    else:
        render_partner_mode()

if __name__ == "__main__":
    main()

