import pandas as pd
import ollama
from langchain_ollama import OllamaEmbeddings
from supabase import create_client, Client
import psycopg2
from dotenv import load_dotenv
import os
import time
from datetime import datetime

# File path for the CSV
file_path = "./synthetic_team_data.csv"
column_names = ['close_notes', 'description', 'u_resolution_tier_2', 'resolved_at', 'sys_created_on']

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST")
SUPABASE_DB_PORT = os.getenv("SUPABASE_DB_PORT")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Step 1: Preprocess the CSV data
def preprocess_data(df):
    try:
        # Handle u_resolution_tier_2: Replace NaN, None, and empty string with mode
        mode_series = df['u_resolution_tier_2'].mode()
        if mode_series.empty:
            raise ValueError("No valid mode found for u_resolution_tier_2: all values are NaN, None, or empty")
        
        mode_value = mode_series[0]
        print(f"Category: {mode_value}")
        df['u_resolution_tier_2'] = df['u_resolution_tier_2'].fillna(mode_value).replace('', mode_value)
        
        # Handle close_notes and description: Replace NaN and None with "Unknown"
        df['close_notes'] = df['close_notes'].fillna("Unknown").replace('', "Unknown")
        df['description'] = df['description'].fillna("Unknown").replace('', "Unknown")
        
        # Handle date columns: Convert to datetime and fill missing values
        df['sys_created_on'] = pd.to_datetime(df['sys_created_on'], errors='coerce')
        df['resolved_at'] = pd.to_datetime(df['resolved_at'], errors='coerce')
        df['sys_created_on'] = df['sys_created_on'].fillna(pd.Timestamp('now'))
        df['resolved_at'] = df['resolved_at'].fillna(pd.Timestamp('now'))
        
        # Calculate resolution time in hours
        df['resolution_time_hours'] = (df['resolved_at'] - df['sys_created_on']).dt.total_seconds() / 3600
        
        # Set a minimum resolution time of 0.1 hours for near-zero or zero values
        df['resolution_time_hours'] = df['resolution_time_hours'].apply(lambda x: max(x, 0.1) if pd.notnull(x) else 0.1)
        
        # Remove duplicate rows based on close_notes and description
        initial_rows = len(df)
        df = df.drop_duplicates(subset=['close_notes', 'description'], keep='first')
        
        return df
    except Exception as e:
        print(f"Error preprocessing data: {e}")
        raise ValueError("Preprocessing failed: Unable to process DataFrame")

# Step 2: Read the CSV file
def read_file(file_path):
    try:
        df = pd.read_csv(file_path, usecols=column_names)
        return df
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None

# Step 3: Extract key information from description
def oneline_solution_summary(text):
    if not isinstance(text, str) or not text.strip():
        print("Description text is empty or invalid.")
        return "close_notes Key Phrase: None"
    
    prompt = """
    Extract key information from the close_notes and format it in one line.
    Input: {text}
    Output format: close_notes Key Phrase: [key phrase]
    Example:
    Input: PDF output misalignment in report generation
    Output: close_notes Key Phrase: PDF output misalignment
    """.format(text=text)
    
    try:
        response = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.get('message', {}).get('content', '').strip() if 'message' in response else \
                  response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if not content:
            print("Unexpected response structure.")
            return "close_notes Key Phrase: None"
        return content
    except Exception as e:
        print(f"Error in ollama.chat for description: {str(e)}")
        return "close_notes Key Phrase: None"

# Generate vectors
def generate_vector(text):
    embedding_model = OllamaEmbeddings(model="mxbai-embed-large")
    if not isinstance(text, str) or not text.strip():
        print("Description text is empty or invalid.")
        return None
    try:
        return embedding_model.embed_query(text)
    except Exception as e:
        print(f"Error generating vector for description: {str(e)}")
        return None

# Store data in Supabase
def store_in_supabase(supabase, data_list):
    try:
        supabase.table("problem_table").delete().gte("id", 0).execute()
        print("Cleared existing documents from Supabase.")
        for idx, (description_content, summary_content, embedding_description, embedding_summary, resolution_tier, issue_created_on, issue_resolved, resolution_time_hours) in enumerate(data_list):
            data = {
                "id": idx + 1,
                "description_content": description_content,
                "summary_content": summary_content,
                "description_vector": embedding_description,
                "solution_vector": embedding_summary,
                "u_resolution_tier_2": resolution_tier,
                "sys_created_on": issue_created_on.isoformat(),
                "resolved_at": issue_resolved.isoformat(),
                "resolution_time_hours": resolution_time_hours,
                "is_valid": True
            }
            response = supabase.table("problem_table").insert(data).execute()
            if not response.data:
                print(f"Warning: No data inserted for ID {idx + 1}")
        print("Data and embeddings stored in Supabase successfully.")
    except Exception as e:
        print(f"Error storing data in Supabase: {e}")

# Search data using raw SQL query
def search_data(user_prompt):
    embedding_model = OllamaEmbeddings(model="mxbai-embed-large")
    user_prompt_vector = generate_vector(user_prompt)

    try:
        conn = psycopg2.connect(
            dbname=SUPABASE_DB_NAME,
            user=SUPABASE_DB_USER,
            password=SUPABASE_DB_PASSWORD,
            host=SUPABASE_DB_HOST,
            port=SUPABASE_DB_PORT
        )
        cur = conn.cursor()

        # Raw SQL query using pgvector's cosine distance (<=>)
        query = """
        SELECT id, description_content, summary_content, u_resolution_tier_2, resolution_time_hours, 1 - (description_vector <=> %s::vector) AS similarity
        FROM problem_table
        ORDER BY description_vector <=> %s::vector
        LIMIT 10;
        """
        
        # Convert vector to string format that PostgreSQL understands
        vector_str = "[" + ",".join(map(str, user_prompt_vector)) + "]"

        cur.execute(query, (vector_str, vector_str))
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return results
    except Exception as e:
        print(f"Error searching data in PostgreSQL: {e}")
        return []

# Calculate approximate resolution time based on historical data
def calculate_approximate_resolution_time(user_prompt, search_results):
    df = read_file(file_path)  # Read CSV to access historical data
    if df is None or df.empty:
        print("No historical data available to calculate resolution time.")
        return None
    
    # Preprocess the data to ensure resolution_time_hours is calculated
    df = preprocess_data(df)
    
    # Determine the category from search results or default to mode
    mode_category = df['u_resolution_tier_2'].mode()[0] if not df['u_resolution_tier_2'].mode().empty else "Unknown"
    category = mode_category
    if search_results:
        top_result_tier = search_results[0][3]  # u_resolution_tier_2 from the first result
        category = top_result_tier if top_result_tier else mode_category
    
    # Filter historical data for the relevant category
    category_data = df[df['u_resolution_tier_2'] == category]
    if category_data.empty:
        print(f"No historical data found for category: {category}")
        return None
    
    # Calculate average resolution time for the category
    resolution_times = category_data['resolution_time_hours'].dropna()
    if resolution_times.empty:
        print(f"No valid resolution times found for category: {category}")
        return None
    
    avg_resolution_time = resolution_times.mean()
    return avg_resolution_time

# Generate final response using LLM
def generate_final_response(user_prompt, search_results):
    # Use the u_resolution_tier_2 of the top result as the category, or default to the mode
    df = read_file(file_path)  # Read CSV to get mode for fallback and calculate trending percentage
    mode_category = df['u_resolution_tier_2'].mode()[0] if not df['u_resolution_tier_2'].mode().empty else "Unknown"
    
    category = mode_category  # Default to mode
    trending_percentage = 0.0
    if df is not None and not df.empty:
        # Calculate trending issue percentage for the category
        total_issues = len(df)
        category_counts = df['u_resolution_tier_2'].value_counts()
        if search_results:
            top_result_tier = search_results[0][3]  # u_resolution_tier_2 from the first result
            category = top_result_tier if top_result_tier else mode_category
        # Calculate percentage of issues in the selected category
        trending_percentage = (category_counts.get(category, 0) / total_issues * 100) if total_issues > 0 else 0.0
    
    # Calculate approximate resolution time
    avg_resolution_time = calculate_approximate_resolution_time(user_prompt, search_results)
    
    # Generate summary for the user prompt using oneline_solution_summary
    prompt_summary = oneline_solution_summary(user_prompt)
    
    # Format search_results into a readable context
    context_lines = ["Prompt Summary: " + prompt_summary, "Search Results:"]
    if not search_results:
        context_lines.append("No relevant results found.")
    else:
        for idx, (id_, description_content, summary_content, u_resolution_tier_2, resolution_time_hours, similarity) in enumerate(search_results, 1):
            result_category = u_resolution_tier_2 if u_resolution_tier_2 else mode_category
            context_lines.append(f"Result {idx}:")
            context_lines.append(f"  ID: {id_}")
            context_lines.append(f"  Description: {description_content}")
            context_lines.append(f"  Summary: {summary_content}")
            context_lines.append(f"  Category: {result_category}")
            context_lines.append(f"  Resolution Time (hours): {resolution_time_hours:.2f}" if resolution_time_hours is not None else "  Resolution Time: Unknown")
            context_lines.append(f"  Similarity: {similarity:.3f}")
            context_lines.append("")
    
    context = "\n".join(context_lines)
    
    # Create the prompt using the formatted search results and prompt summary as context
    prompt = """
    Based on the following context, provide a concise response to the query: {}

    Context:
    {}

    The context contains a summarized key phrase of the query (Prompt Summary) and search results with ID, Description, Summary, Category (from u_resolution_tier_2), Resolution Time (in hours), and Similarity (relevance to the query). Provide a clear and concise response followed by a list of actionable steps to resolve the issue. Base the response and steps on the Prompt Summary and search results. If specific details are missing, provide general guidance based on the context and category, without referencing specific result IDs, similarity scores, or suggesting to explore other results. Only state that the context is irrelevant if no results are provided. Avoid responding with 'I don't know' or 'no exact match found.' Format the response as:
    Response: [Your concise response]
    Actionable Steps:
    - [Step 1]
    - [Step 2]
    - [Step 3]
    """.format(user_prompt, context)
    
    # System message to encourage concise, actionable responses
    system_message = """
    You are a helpful assistant. Provide a concise response to the query based on the provided context, which contains a summarized key phrase of the query (Prompt Summary) and search results with ID, Description, Summary, Category, Resolution Time (in hours), and Similarity. Analyze the Prompt Summary and search results to generate a clear response followed by a list of actionable steps to resolve the issue. If specific details are missing, offer general guidance based on the context and category, without referencing specific result IDs, similarity scores, or suggesting to explore other results. Only state that the context is irrelevant if no results are provided. Do not respond with 'I don't know' or 'no exact match found.' Format the response as:
    Response: [Your concise response]
    Actionable Steps:
    - [Step 1]
    - [Step 2]
    - [Step 3]
    """
    
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.get('message', {}).get('content', '').strip() if 'message' in response else \
                  response.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if not content:
            print("Unexpected response structure from LLM.")
            content = """Response: Please provide more details or check the system documentation for guidance.
Actionable Steps:
- Review the system documentation.
- Verify input data for accuracy.
- Contact support if the issue persists."""
        
        # Format the final response in the requested arrangement
        final_response_lines = [
            content,
            f"Resolution Category: {category}",
            f"Estimated Resolution Time: {avg_resolution_time:.2f} hours" if avg_resolution_time is not None else "Estimated Resolution Time: Unknown (no historical data for this category)",
            f"Trending Issue Percentage: {trending_percentage:.2f}%"
        ]
        
        final_response = "\n".join(final_response_lines)
        return final_response
    except Exception as e:
        print(f"Error in generating final response: {e}")
        final_response_lines = [
            "Response: Error generating response. Please try again or check the system logs.",
            "Actionable Steps:",
            "- Check system logs for errors.",
            "- Verify input data.",
            "- Contact support if the issue persists.",
            f"Resolution Category: {category}",
            f"Estimated Resolution Time: {avg_resolution_time:.2f} hours" if avg_resolution_time is not None else "Estimated Resolution Time: Unknown (no historical data for this category)",
            f"Trending Issue Percentage: {trending_percentage:.2f}%"
        ]
        return "\n".join(final_response_lines)

def store_csvfile_into_database(file_path):
    df = read_file(file_path)
    if df is not None:
        # Preprocess the data to handle NaN, None, or empty values and duplicates
        df = preprocess_data(df)
        
        print("\nResults of oneline_solution_summary for each row:")
        data_to_store = []
        for index, row in df.iterrows():
            result = oneline_solution_summary(row['close_notes'])
            description = row['description']
            summary = result + " " + description
            resolution_tier = row['u_resolution_tier_2']
            issue_created_on = row['sys_created_on']
            issue_resolved = row['resolved_at']
            resolution_time_hours = row['resolution_time_hours']
            
            embedding_description = generate_vector(description)
            embedding_summary = generate_vector(summary)
            
            if embedding_description is None or embedding_summary is None:
                print(f"Skipping row {index} due to invalid embeddings.")
                continue
            
            data_to_store.append((description, summary, embedding_description, embedding_summary, resolution_tier, issue_created_on, issue_resolved, resolution_time_hours))
        
        # Store embeddings in Supabase
        store_in_supabase(supabase, data_to_store)
        print("Embeddings storage process completed.")
    else:
        print("No data found in the CSV file.")

def main():
    # Uncomment to store CSV data into the database
    # store_csvfile_into_database(file_path)
    
    # Get user prompt and search
    user_prompt = input("Enter your prompt: ")
    results = search_data(user_prompt)
    
    # Generate and print final response first
    final_response = generate_final_response(user_prompt, results)
    print("\nFinal Response:")
    print(final_response)
    
    # Print search results afterward
    print("\nSearch Results:")
    for result in results:
        print(result)

if __name__ == "__main__":
    main()