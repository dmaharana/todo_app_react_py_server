import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np
from typing import List, Dict, Optional, Tuple
import openai  # or your preferred embedding provider
from dataclasses import dataclass
import logging

@dataclass
class BugData:
    incident_number: str
    product: str
    description: str
    closing_notes: Optional[str] = None
    resolution_tier_1: Optional[str] = None
    resolution_tier_2: Optional[str] = None
    resolution_tier_3: Optional[str] = None
    problem_id: Optional[str] = None

class BugRAGSystem:
    def __init__(self, db_config: Dict[str, str], embedding_model: str = "text-embedding-3-small"):
        self.db_config = db_config
        self.embedding_model = embedding_model
        self.embedding_dimension = 1536  # Adjust based on your model
        
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for given text using OpenAI API"""
        try:
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            raise
    
    def store_bug(self, bug_data: BugData) -> int:
        """Store bug data and generate embeddings"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Insert bug data
                insert_bug_query = """
                    INSERT INTO bugs (
                        incident_number, product, description, closing_notes,
                        resolution_tier_1, resolution_tier_2, resolution_tier_3, problem_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                cursor.execute(insert_bug_query, (
                    bug_data.incident_number,
                    bug_data.product,
                    bug_data.description,
                    bug_data.closing_notes,
                    bug_data.resolution_tier_1,
                    bug_data.resolution_tier_2,
                    bug_data.resolution_tier_3,
                    bug_data.problem_id
                ))
                bug_id = cursor.fetchone()[0]
                
                # Generate and store embeddings
                self._store_embeddings(cursor, bug_id, bug_data)
                
                conn.commit()
                return bug_id
    
    def _store_embeddings(self, cursor, bug_id: int, bug_data: BugData):
        """Generate and store different types of embeddings"""
        embedding_configs = [
            ("description", bug_data.description),
        ]
        
        # Add resolution embedding if closing notes exist
        if bug_data.closing_notes:
            resolution_text = f"Resolution: {bug_data.closing_notes}"
            if bug_data.resolution_tier_1:
                resolution_text += f" | Tier 1: {bug_data.resolution_tier_1}"
            if bug_data.resolution_tier_2:
                resolution_text += f" | Tier 2: {bug_data.resolution_tier_2}"
            if bug_data.resolution_tier_3:
                resolution_text += f" | Tier 3: {bug_data.resolution_tier_3}"
            embedding_configs.append(("resolution", resolution_text))
        
        # Add combined embedding
        combined_text = f"Product: {bug_data.product} | Description: {bug_data.description}"
        if bug_data.closing_notes:
            combined_text += f" | Resolution: {bug_data.closing_notes}"
        embedding_configs.append(("combined", combined_text))
        
        # Generate and store embeddings
        for content_type, text in embedding_configs:
            embedding = self.generate_embedding(text)
            cursor.execute("""
                INSERT INTO bug_embeddings (bug_id, content_type, content_text, embedding)
                VALUES (%s, %s, %s, %s)
            """, (bug_id, content_type, text, embedding))
    
    def search_similar_bugs(
        self,
        query: str,
        content_type: Optional[str] = None,
        product_filter: Optional[str] = None,
        similarity_threshold: float = 0.7,
        limit: int = 10
    ) -> List[Dict]:
        """Search for similar bugs using semantic similarity"""
        query_embedding = self.generate_embedding(query)
        
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM search_similar_bugs(%s, %s, %s, %s, %s)
                """, (query_embedding, content_type, product_filter, similarity_threshold, limit))
                
                return [dict(row) for row in cursor.fetchall()]
    
    def get_bug_by_incident_number(self, incident_number: str) -> Optional[Dict]:
        """Retrieve bug by incident number"""
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM bugs WHERE incident_number = %s
                """, (incident_number,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
    
    def get_bugs_by_resolution_tier(
        self,
        tier_level: int,
        tier_value: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get bugs by resolution tier"""
        column_map = {
            1: "resolution_tier_1",
            2: "resolution_tier_2", 
            3: "resolution_tier_3"
        }
        
        if tier_level not in column_map:
            raise ValueError("tier_level must be 1, 2, or 3")
        
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = f"""
                    SELECT * FROM bugs 
                    WHERE {column_map[tier_level]} = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """
                cursor.execute(query, (tier_value, limit))
                
                return [dict(row) for row in cursor.fetchall()]
    
    def hybrid_search(
        self,
        query: str,
        product: Optional[str] = None,
        resolution_tiers: Optional[Dict[int, str]] = None,
        similarity_threshold: float = 0.6,
        limit: int = 10
    ) -> List[Dict]:
        """Hybrid search combining semantic similarity with metadata filtering"""
        query_embedding = self.generate_embedding(query)
        
        where_conditions = ["(1 - (be.embedding <=> %s)) >= %s"]
        params = [query_embedding, similarity_threshold]
        
        if product:
            where_conditions.append("b.product = %s")
            params.append(product)
        
        if resolution_tiers:
            for tier_level, tier_value in resolution_tiers.items():
                if tier_level in [1, 2, 3]:
                    where_conditions.append(f"b.resolution_tier_{tier_level} = %s")
                    params.append(tier_value)
        
        params.append(limit)
        
        query = f"""
            SELECT 
                b.incident_number,
                b.product,
                b.description,
                b.closing_notes,
                b.resolution_tier_1,
                b.resolution_tier_2,
                b.resolution_tier_3,
                b.problem_id,
                1 - (be.embedding <=> %s) as similarity_score,
                be.content_type
            FROM bugs b
            JOIN bug_embeddings be ON b.id = be.bug_id
            WHERE {' AND '.join(where_conditions)}
            ORDER BY be.embedding <=> %s
            LIMIT %s
        """
        
        # Duplicate query_embedding for ORDER BY clause
        params.insert(-1, query_embedding)
        
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
    
    def bulk_insert_bugs(self, bugs: List[BugData], batch_size: int = 100):
        """Bulk insert bugs with embeddings"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                for i in range(0, len(bugs), batch_size):
                    batch = bugs[i:i + batch_size]
                    
                    # Insert bugs
                    bug_values = []
                    for bug in batch:
                        bug_values.append((
                            bug.incident_number,
                            bug.product,
                            bug.description,
                            bug.closing_notes,
                            bug.resolution_tier_1,
                            bug.resolution_tier_2,
                            bug.resolution_tier_3,
                            bug.problem_id
                        ))
                    
                    cursor.executemany("""
                        INSERT INTO bugs (
                            incident_number, product, description, closing_notes,
                            resolution_tier_1, resolution_tier_2, resolution_tier_3, problem_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, bug_values)
                    
                    # Get inserted IDs and generate embeddings
                    cursor.execute("""
                        SELECT id, incident_number FROM bugs 
                        WHERE incident_number = ANY(%s)
                    """, ([bug.incident_number for bug in batch],))
                    
                    bug_id_map = {row[1]: row[0] for row in cursor.fetchall()}
                    
                    # Generate embeddings for batch
                    for bug in batch:
                        bug_id = bug_id_map[bug.incident_number]
                        self._store_embeddings(cursor, bug_id, bug)
                    
                    conn.commit()
                    logging.info(f"Processed {i + len(batch)} bugs")

# Usage example
if __name__ == "__main__":
    # Database configuration
    db_config = {
        "host": "localhost",
        "database": "bug_rag_db",
        "user": "your_user",
        "password": "your_password",
        "port": "5432"
    }
    
    # Initialize RAG system
    rag_system = BugRAGSystem(db_config)
    
    # Example: Store a bug
    bug = BugData(
        incident_number="INC-12345",
        product="WebApp",
        description="Login page crashes when user enters special characters",
        closing_notes="Fixed input validation to handle special characters properly",
        resolution_tier_1="Technical",
        resolution_tier_2="Frontend",
        resolution_tier_3="Input Validation"
    )
    
    bug_id = rag_system.store_bug(bug)
    print(f"Stored bug with ID: {bug_id}")
    
    # Example: Search for similar bugs
    similar_bugs = rag_system.search_similar_bugs(
        query="login issues with special characters",
        similarity_threshold=0.7,
        limit=5
    )
    
    print(f"Found {len(similar_bugs)} similar bugs:")
    for bug in similar_bugs:
        print(f"- {bug['incident_number']}: {bug['description'][:100]}... (similarity: {bug['similarity_score']:.3f})")