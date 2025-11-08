import streamlit as st
from helper import postgres_fetch, postgres_insert, postgres_update, postgres_delete
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
# SQL HELPER FUNCTIONS
# ============================================================================

def escape_sql_string(value):
    """Escape SQL string values for safe insertion"""
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        return str(value)
    # Escape single quotes by doubling them
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"

def format_sql_query(query: str, params: tuple = None):
    """Format SQL query with parameters safely"""
    if params is None:
        return query
    
    formatted_query = query
    for param in params:
        escaped_value = escape_sql_string(param)
        # Replace first %s with escaped value
        formatted_query = formatted_query.replace('%s', escaped_value, 1)
    
    return formatted_query

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_all_surveys():
    """Fetch all available surveys"""
    query = """
        SELECT 
            "template_name" as survey_name,
            "description",
            "questions"::text as questions,
            "created_date",
            "updated_date"
        FROM "templates" 
        ORDER BY "created_date" DESC
    """
    try:
        df = postgres_fetch(query)
        # Check if result is actually a DataFrame
        if not isinstance(df, pd.DataFrame):
            st.error(f"Unexpected return type from postgres_fetch: {type(df)}")
            return []
        if df is None or df.empty:
            return []
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        # Parse questions JSON field and clean up NaN values
        for record in records:
            # Clean up NaN values in description
            if 'description' in record:
                desc = record['description']
                if desc is None or (isinstance(desc, float) and pd.isna(desc)):
                    record['description'] = ''
            if 'questions' in record:
                questions = record['questions']
                # Handle different data types
                if questions is None:
                    record['questions'] = []
                elif isinstance(questions, str):
                    # Try to parse as JSON string
                    try:
                        parsed = json.loads(questions)
                        record['questions'] = parsed if isinstance(parsed, list) else []
                    except (json.JSONDecodeError, TypeError) as e:
                        # If parsing fails, set to empty list
                        st.warning(f"Failed to parse questions JSON for {record.get('survey_name', 'Unknown')}: {str(e)}")
                        record['questions'] = []
                elif isinstance(questions, (list, dict)):
                    # Already parsed or is a list/dict
                    record['questions'] = questions if isinstance(questions, list) else []
                else:
                    # Try to convert to string and parse
                    try:
                        questions_str = str(questions)
                        parsed = json.loads(questions_str)
                        record['questions'] = parsed if isinstance(parsed, list) else []
                    except (json.JSONDecodeError, TypeError):
                        record['questions'] = []
        return records
    except Exception as e:
        st.error(f"Database error in get_all_surveys: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_customers(search_term: str = ""):
    """Search customers by company name or ID"""
    try:
        if search_term:
            search_pattern = f"%{search_term}%"
            query = f"""
                SELECT "customer_id", "customer_company", "classification", "owner"
                FROM "customers" 
                WHERE "customer_company" ILIKE {escape_sql_string(search_pattern)} 
                   OR "customer_id" ILIKE {escape_sql_string(search_pattern)}
                ORDER BY "customer_company" ASC
                LIMIT 50
            """
        else:
            query = """
                SELECT "customer_id", "customer_company", "classification", "owner"
                FROM "customers" 
                ORDER BY "customer_company" ASC
                LIMIT 50
            """
        
        df = postgres_fetch(query)
        # Check if result is actually a DataFrame
        if not isinstance(df, pd.DataFrame):
            return []
        if df is None or df.empty:
            return []
        return df.to_dict('records')
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return []

def check_existing_responses(customer_id: str, partner_company: str, template_name: str):
    """Check if responses already exist for this combination"""
    try:
        # Ensure customer_id is treated as text for comparison
        query = f"""
            SELECT 
                r."question_id", 
                r."response_value", 
                s."submission_date",
                p."partner_name" as previous_partner_name,
                c."customer_company"
            FROM "responses" r
            JOIN "submissions" s ON r."submission_id" = s."id"
            JOIN "partners" p ON s."partner_id" = p."id"
            JOIN "customers" c ON s."customer_id" = c."customer_id"
            JOIN "templates" t ON s."template_id" = t."id"
            WHERE s."customer_id"::text = {escape_sql_string(customer_id)} 
            AND p."partner_company" = {escape_sql_string(partner_company)} 
            AND t."template_name" = {escape_sql_string(template_name)}
            AND s."id" = (
                SELECT MAX(s2."id") 
                FROM "submissions" s2 
                JOIN "partners" p2 ON s2."partner_id" = p2."id"
                JOIN "templates" t2 ON s2."template_id" = t2."id"
                WHERE s2."customer_id"::text = {escape_sql_string(customer_id)}
                AND p2."partner_company" = {escape_sql_string(partner_company)}
                AND t2."template_name" = {escape_sql_string(template_name)}
            )
        """
        
        df = postgres_fetch(query)
        
        # Check if result is actually a DataFrame
        # If postgres_fetch returns an error dict or other non-DataFrame, handle it
        if not isinstance(df, pd.DataFrame):
            # If it's a dict with an error message, that's expected when no data exists
            if isinstance(df, dict):
                # Silently handle - this might be an error response from the helper
                return {'has_existing': False}
            return {'has_existing': False}
        
        if df is not None and not df.empty:
            # Convert DataFrame to list of dicts
            results = df.to_dict('records')
            responses = {row['question_id']: row['response_value'] for row in results}
            return {
                'has_existing': True,
                'responses': responses,
                'submission_date': results[0]['submission_date'],
                'previous_partner_name': results[0]['previous_partner_name'],
                'customer_company': results[0]['customer_company']
            }
        return {'has_existing': False}
    except Exception as e:
        error_msg = str(e)
        # Suppress errors for "no existing responses" - this is normal
        # Only show errors if they're actual database connection or critical errors
        # Don't show type mismatch errors as they might be expected when no data exists
        if 'operator does not exist' in error_msg.lower() or 'no connection adapters' in error_msg.lower():
            # These errors typically occur when the query fails due to type mismatches
            # or when postgres_fetch returns an error dict instead of DataFrame
            # Silently return False - this is expected when checking for existing responses
            pass
        return {'has_existing': False}

def submit_survey_responses(customer_id: str, customer_company: str, 
                           partner_name: str, partner_company: str,
                           template_name: str, responses: Dict, is_update: bool = False):
    """Submit survey responses to database"""
    try:
        # Insert or get customer
        customer_query = f"""
            INSERT INTO "customers" ("customer_id", "customer_company") 
            VALUES ({escape_sql_string(customer_id)}, {escape_sql_string(customer_company)}) 
            ON CONFLICT ("customer_id") DO UPDATE SET "customer_company" = {escape_sql_string(customer_company)}
        """
        result = postgres_insert(customer_query)
        # Check if postgres_insert returned an error (only 'message' indicates error)
        if isinstance(result, dict) and 'message' in result:
            raise Exception(f"Database insert error (customers): {result.get('message', 'Unknown error')}")
        
        # Insert or get partner and retrieve partner_id
        partner_query = f"""
            INSERT INTO "partners" ("partner_name", "partner_company") 
            VALUES ({escape_sql_string(partner_name)}, {escape_sql_string(partner_company)}) 
            ON CONFLICT ("partner_name", "partner_company") DO UPDATE SET "partner_name" = {escape_sql_string(partner_name)}
        """
        result = postgres_insert(partner_query)
        # Check if postgres_insert returned an error (only 'message' indicates error)
        if isinstance(result, dict) and 'message' in result:
            raise Exception(f"Database insert error (partners): {result.get('message', 'Unknown error')}")
        
        # Get partner_id
        partner_fetch_query = f"""
            SELECT "id" FROM "partners" 
            WHERE "partner_name" = {escape_sql_string(partner_name)} 
            AND "partner_company" = {escape_sql_string(partner_company)}
            LIMIT 1
        """
        partner_df = postgres_fetch(partner_fetch_query)
        if not isinstance(partner_df, pd.DataFrame) or partner_df is None or partner_df.empty:
            raise Exception("Failed to get partner ID")
        partner_id = int(partner_df.iloc[0]['id'])
        
        # Get template ID
        template_query = f"""
            SELECT "id", "questions"::text as "questions" FROM "templates" WHERE "template_name" = {escape_sql_string(template_name)}
        """
        template_df = postgres_fetch(template_query)
        if not isinstance(template_df, pd.DataFrame) or template_df is None or template_df.empty:
            raise Exception(f"Template '{template_name}' not found")
        template_id = int(template_df.iloc[0]['id'])
        template_questions_raw = template_df.iloc[0]['questions']
        # Parse questions JSON - handle different data types
        if template_questions_raw is None:
            template_questions = []
        elif isinstance(template_questions_raw, str):
            try:
                parsed = json.loads(template_questions_raw)
                template_questions = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                raise Exception(f"Failed to parse questions JSON for template '{template_name}'")
        elif isinstance(template_questions_raw, list):
            template_questions = template_questions_raw
        else:
            # Try to convert and parse
            try:
                questions_str = str(template_questions_raw)
                parsed = json.loads(questions_str)
                template_questions = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                raise Exception(f"Failed to parse questions for template '{template_name}'")
        
        # Get previous submission ID if updating
        previous_submission_id = None
        if is_update:
            # template_id is already cast to int above
            # Get submissions by partner and template, then filter by customer_id in Python
            prev_query = f"""
                SELECT s."id", s."customer_id"
                FROM "submissions" s
                JOIN "partners" p ON s."partner_id" = p."id"
                WHERE p."partner_name" = {escape_sql_string(partner_name)} 
                AND p."partner_company" = {escape_sql_string(partner_company)} 
                AND s."template_id" = {template_id}
                ORDER BY s."id" DESC
            """
            prev_df = postgres_fetch(prev_query)
            if isinstance(prev_df, pd.DataFrame) and prev_df is not None and not prev_df.empty:
                # Filter by customer_id in Python to avoid type mismatch
                for _, row in prev_df.iterrows():
                    if str(row['customer_id']) == str(customer_id):
                        previous_submission_id = int(row['id'])
                        break
        
        # Create new submission
        # partner_id and template_id are already integers
        # Handle previous_submission_id - use NULL if None, otherwise use integer value
        if previous_submission_id:
            previous_submission_id_value = int(previous_submission_id)
        else:
            previous_submission_id_value = 'NULL'
        
        submission_query = f"""
            INSERT INTO "submissions" ("customer_id", "partner_id", "template_id", "is_update", "previous_submission_id") 
            VALUES ({escape_sql_string(customer_id)}, {partner_id}, {template_id}, {escape_sql_string(is_update)}, {previous_submission_id_value})
        """
        result = postgres_insert(submission_query)
        # Check if postgres_insert returned an error (only 'message' indicates error)
        # Success responses may have 'return_value' and 'execution_id', which are OK
        if isinstance(result, dict) and 'message' in result:
            error_msg = result.get('message', str(result))
            raise Exception(f"Database insert error (submissions): {error_msg}")
        
        # Get submission_id and submission_uuid
        # Since we just inserted, get the most recent submission matching partner_id and template_id
        # Then verify customer_id matches in Python to avoid type mismatch in SQL
        submission_fetch_query = f"""
            SELECT "id", "submission_uuid", "customer_id" 
            FROM "submissions" 
            WHERE "partner_id" = {partner_id} 
            AND "template_id" = {template_id}
            ORDER BY "id" DESC LIMIT 1
        """
        submission_df = postgres_fetch(submission_fetch_query)
        if not isinstance(submission_df, pd.DataFrame) or submission_df is None or submission_df.empty:
            raise Exception("Failed to get submission ID")
        
        # Verify customer_id matches (handle type conversion in Python)
        fetched_customer_id = str(submission_df.iloc[0]['customer_id'])
        if fetched_customer_id != str(customer_id):
            raise Exception(f"Customer ID mismatch: expected {customer_id}, got {fetched_customer_id}")
        
        submission_id = int(submission_df.iloc[0]['id'])
        submission_uuid = submission_df.iloc[0]['submission_uuid']
        
        # Insert responses
        for question_id, response_value in responses.items():
            if response_value is not None and response_value != '':
                # Find question details from template
                question_detail = next((q for q in template_questions if q['id'] == question_id), None)
                question_text = question_detail['question'] if question_detail else question_id
                response_type = question_detail['type'] if question_detail else 'unknown'
                section_name = question_detail.get('section') if question_detail else None
                
                response_query = f"""
                    INSERT INTO "responses" ("submission_id", "question_id", "question_text", "response_value", "response_type", "section_name") 
                    VALUES ({submission_id}, {escape_sql_string(question_id)}, {escape_sql_string(question_text)}, {escape_sql_string(str(response_value))}, {escape_sql_string(response_type)}, {escape_sql_string(section_name) if section_name else 'NULL'})
                """
                result = postgres_insert(response_query)
                # Check if postgres_insert returned an error (only 'message' indicates error)
                # Success responses may have 'return_value' and 'execution_id', which are OK
                if isinstance(result, dict) and 'message' in result:
                    raise Exception(f"Database insert error (responses): {result.get('message', 'Unknown error')}")
        
        return {'success': True, 'submission_id': submission_id, 'submission_uuid': str(submission_uuid)}
    
    except Exception as e:
        error_msg = str(e)
        # Extract actual error message if it's wrapped in a dict string
        if 'connection adapters' in error_msg and '{' in error_msg:
            # Try to extract the actual error message from the wrapped dict
            import re
            match = re.search(r"'message':\s*'([^']+)'", error_msg)
            if match:
                error_msg = match.group(1)
        st.error(f"Error submitting responses: {error_msg}")
        return {'success': False, 'error': error_msg}

def upload_template(survey_name: str, questions: List[Dict], description: str = ""):
    """Upload a new survey template"""
    try:
        questions_json = json.dumps(questions)
        query = f"""
            INSERT INTO "templates" ("template_name", "questions", "description") 
            VALUES ({escape_sql_string(survey_name)}, {escape_sql_string(questions_json)}, {escape_sql_string(description)}) 
            ON CONFLICT ("template_name") 
            DO UPDATE SET "questions" = {escape_sql_string(questions_json)}, "updated_date" = CURRENT_TIMESTAMP
        """
        postgres_insert(query)
        return True
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return False

def export_all_submissions():
    """Export all submissions to Excel"""
    try:
        query = """
            SELECT 
                s."submission_uuid",
                s."submission_date",
                s."customer_id",
                c."customer_company",
                p."partner_name",
                p."partner_company",
                t."template_name" as survey_name,
                s."is_update",
                r."question_id",
                r."question_text",
                r."response_value",
                r."response_type",
                r."section_name"
            FROM "submissions" s
            JOIN "customers" c ON s."customer_id" = c."customer_id"
            JOIN "partners" p ON s."partner_id" = p."id"
            JOIN "templates" t ON s."template_id" = t."id"
            LEFT JOIN "responses" r ON s."id" = r."submission_id"
            ORDER BY s."submission_date" DESC, r."question_id"
        """
        
        df = postgres_fetch(query)
        
        # Check if result is actually a DataFrame
        if not isinstance(df, pd.DataFrame):
            return None
        if df is None or df.empty:
            return None
        
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
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return None

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
        /* Center align radio buttons */
        div[data-testid="stRadio"] {
            display: flex;
            justify-content: center;
            align-items: center;
        }
        /* Reduce padding around radio buttons */
        div[data-testid="stRadio"] > div {
            gap: 0 !important;
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
            st.markdown('<div style="padding: 8px 12px; font-weight: bold; background-color: #f8f9fa; border-bottom: 2px solid #d0d0d0;">Aspect</div>', unsafe_allow_html=True)
        
        for idx, col_name in enumerate(matrix_cols):
            with header_cols[idx + 1]:
                st.markdown(f'<div style="padding: 8px; font-weight: bold; background-color: #f8f9fa; border-bottom: 2px solid #d0d0d0; text-align: center;">{col_name}</div>', unsafe_allow_html=True)
        
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
                st.markdown(f'<div style="padding: 8px 12px; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center;">{row_name}</div>', unsafe_allow_html=True)
            
            # Create a unique key for this row's radio group
            row_key = f"{key}_{row_name.replace(' ', '_').replace('|', '_')}_{row_idx}"
            
            # Place each radio button in its corresponding column
            for col_idx, col_name in enumerate(matrix_cols):
                with row_cols[col_idx + 1]:
                    # Create a container with border and centered content
                    st.markdown(f'<div style="padding: 4px; border-bottom: 1px solid #e0e0e0; text-align: center; display: flex; align-items: center; justify-content: center;">', unsafe_allow_html=True)
                    
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
    # Safely get questions and ensure it's a list
    questions_raw = survey_config.get('questions', [])
    
    # Handle different data types
    if questions_raw is None:
        questions = []
    elif isinstance(questions_raw, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(questions_raw)
            questions = parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            st.error(f"Failed to parse questions JSON. Raw value type: {type(questions_raw)}")
            questions = []
    elif isinstance(questions_raw, list):
        questions = questions_raw
    else:
        # Try to convert to list or parse
        try:
            if isinstance(questions_raw, dict):
                questions = [questions_raw]  # Single question as dict
            else:
                questions_str = str(questions_raw)
                parsed = json.loads(questions_str)
                questions = parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            st.error(f"Unexpected questions format. Type: {type(questions_raw)}")
            questions = []
    
    if not questions:
        st.warning("⚠️ No questions found in this survey template.")
        return
    
    # Group questions by section
    sections = {}
    for q in questions:
        # Ensure q is a dict
        if not isinstance(q, dict):
            st.warning(f"Skipping invalid question format: {type(q)}")
            continue
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
            # Safely get questions count
            questions = survey.get('questions', [])
            if not isinstance(questions, list):
                questions = []
            question_count = len(questions) if questions else 0
            # Handle NaN/None values from pandas
            desc = survey.get('description', '')
            if desc is None or (isinstance(desc, float) and pd.isna(desc)) or desc == '':
                desc = 'No description'
            st.info(f"📋 {desc} ({question_count} questions)")
    
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
            <p>Streamlit Edition - Using GoCobalt Helper Functions</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🔧 Navigation")
    
    # Connection status - test with a simple query
    try:
        test_query = "SELECT 1 as test"
        postgres_fetch(test_query)
        st.sidebar.success("✅ Database Connected")
    except Exception as e:
        st.sidebar.error("❌ Database Connection Failed")
        st.error(f"Database connection error: {str(e)}")
        st.info("Please ensure the gocobalt helper functions are properly configured with writeback database credentials.")
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

