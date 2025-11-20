import json
import os
import re
from pathlib import Path
from typing import List, Tuple
from bs4 import BeautifulSoup
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    UnstructuredFileLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.documents import Document
from backend.models import TestPlan, TestCase

# Persistence directory for Chroma
CHROMA_PATH = "data/chroma_db"
UPLOAD_DIR = "data/uploads"

class RAGEngine:
    def __init__(self):
        # Initialize Embeddings (using a local model to avoid API costs for embeddings)
        self.embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Initialize Vector Store
        self.vector_store = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=self.embedding_function
        )
        self.latest_html_path: str | None = None
        self.latest_html_content: str | None = None
        
    def _get_llm(self, api_key: str = None):
        # Use provided key, or fall back to env var, or placeholder
        final_key = api_key or os.getenv("GOOGLE_API_KEY", "AIza-placeholder")
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0,
            google_api_key=final_key
        )

    def ingest_documents(self, file_paths: List[str]):
        documents: List[Document] = []
        for file_path in file_paths:
            docs = self._load_with_metadata(file_path)
            documents.extend(docs)

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
        chunks = text_splitter.split_documents(documents)
        self.vector_store.add_documents(chunks)
        return len(chunks)

    def _load_with_metadata(self, file_path: str) -> List[Document]:
        ext = Path(file_path).suffix.lower()
        base_metadata = {
            "source_document": os.path.basename(file_path),
            "doc_type": "html" if ext in {".html", ".htm"} else "support"
        }

        if ext == ".md":
            loader = UnstructuredMarkdownLoader(file_path)
            docs = loader.load()
        elif ext in {".txt"}:
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()
        elif ext in {".json"}:
            docs = self._load_json(file_path, base_metadata)
        elif ext in {".html", ".htm"}:
            docs = self._load_html(file_path, base_metadata)
        elif ext in {".pdf"}:
            loader = UnstructuredFileLoader(file_path)
            docs = loader.load()
        else:
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()

        for doc in docs:
            doc.metadata.setdefault("source_document", base_metadata["source_document"])
            doc.metadata.setdefault("doc_type", base_metadata["doc_type"])

        return docs

    def _load_json(self, file_path: str, metadata: dict) -> List[Document]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        flattened = json.dumps(data, indent=2)
        return [Document(page_content=flattened, metadata=metadata)]

    def _load_html(self, file_path: str, metadata: dict) -> List[Document]:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_html = f.read()
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator="\n")
        self.latest_html_path = file_path
        self.latest_html_content = raw_html
        return [Document(page_content=text, metadata=metadata)]

    def clear_database(self):
        try:
            # Try to delete the collection directly to avoid file lock issues on Windows
            self.vector_store.delete_collection()
        except Exception as e:
            print(f"Warning: Could not delete collection: {e}")
        
        # Re-initialize to ensure we have a fresh start (and create collection if needed)
        self.vector_store = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=self.embedding_function
        )
        self.latest_html_path = None
        self.latest_html_content = None

    def generate_test_cases(self, query: str, api_key: str = None) -> TestPlan:
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 6})
        context_docs = retriever.invoke(query)
        allowed_sources = self._collect_sources(context_docs)
        context_text = self._format_docs(context_docs)

        llm = self._get_llm(api_key)
        template = """You are an expert QA Automation Engineer.
        The retrieved context snippets are each prefixed with [Source:<filename>].
        Use ONLY this information to build:
        - A list called "test_viewpoints" describing 3-5 distinct ways to look at the system under test.
        - A "test_cases" list with detailed cases grounded in the sources.

        Context:
        {context}

        User Request: {query}

        Rules:
        1. Do not invent features that are not explicitly mentioned.
        2. Every test case must include: "test_id", "feature", "test_scenario", "expected_result", "grounded_in".
        3. The "grounded_in" value must match one of the source filenames in the context.
        4. Provide at least one positive and one negative scenario when the context allows it.
        5. Return valid JSON with keys: "test_viewpoints" and "test_cases".
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        parser = JsonOutputParser(pydantic_object=TestPlan)

        chain = prompt | llm | parser
        result = chain.invoke({"context": context_text, "query": query})
        test_plan = TestPlan(**result)
        self._validate_grounding(test_plan, allowed_sources)
        return test_plan

    def generate_selenium_script(self, test_case: TestCase, html_content: str | None = None, api_key: str = None) -> str:
        support_retriever = self.vector_store.as_retriever(search_kwargs={"k": 3, "filter": {"doc_type": "support"}})
        docs = support_retriever.invoke(test_case.feature)
        html_context_docs = self._get_html_documents()
        combined_context = self._format_docs(docs + html_context_docs)

        html_source = html_content or self._get_latest_html_content()
        if not html_source:
            raise ValueError("No checkout HTML is available. Rebuild the knowledge base with checkout.html included.")
        llm = self._get_llm(api_key)

        template = """You are an expert Python Selenium Developer.
        Generate a complete, runnable Python Selenium script for the following test case.
        
        Test Case:
        ID: {test_id}
        Scenario: {scenario}
        Expected Result: {expected}
        
        Target HTML Page Source:
        {html_content}
        
        Relevant Documentation Context:
        {context}
        
        Requirements:
        1. Use 'webdriver.Chrome()'.
        2. Assume the HTML file is located at 'file:///path/to/checkout.html' (use a placeholder path).
        3. Use explicit waits (WebDriverWait) instead of sleep where possible.
        4. Use precise selectors based on the provided HTML (IDs, classes, names).
        5. Include assertions to verify the Expected Result and echo the success message when appropriate.
        6. Return ONLY the Python code, no markdown formatting.
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        chain = prompt | llm | StrOutputParser()
        
        script = chain.invoke({
            "test_id": test_case.test_id,
            "scenario": test_case.test_scenario,
            "expected": test_case.expected_result,
            "html_content": html_source,
            "context": combined_context
        })
        
        # Clean up markdown code blocks if present
        script = script.replace("```python", "").replace("```", "").strip()
        self._validate_selenium_script(script, html_source)
        return script

    def _format_docs(self, docs: List[Document]) -> str:
        if not docs:
            return ""
        formatted = []
        for doc in docs:
            source = doc.metadata.get("source_document", "unknown")
            formatted.append(f"[Source:{source}]\n{doc.page_content.strip()}" )
        return "\n\n".join(formatted)

    def _collect_sources(self, docs: List[Document]) -> set:
        return {doc.metadata.get("source_document", "unknown") for doc in docs if doc.metadata.get("source_document")}

    def _validate_grounding(self, test_plan: TestPlan, allowed_sources: set):
        if not allowed_sources:
            return
        invalid_cases = []
        for case in test_plan.test_cases:
            grounded = (case.grounded_in or "").strip()
            if grounded not in allowed_sources:
                invalid_cases.append((case.test_id, grounded))
        if invalid_cases:
            detail = ", ".join([f"{tid}:{src or 'missing'}" for tid, src in invalid_cases])
            raise ValueError(f"Grounding validation failed. Unknown sources referenced: {detail}")

    def _validate_selenium_script(self, script: str, html_source: str):
        soup = BeautifulSoup(html_source, "html.parser")
        html_ids = {tag.get("id") for tag in soup.find_all(id=True) if tag.get("id")}
        html_names = {tag.get("name") for tag in soup.find_all(attrs={"name": True}) if tag.get("name")}
        html_classes = set()
        for tag in soup.find_all(class_=True):
            classes = tag.get("class", [])
            for cls in classes:
                html_classes.add(cls)

        selector_pattern = re.compile(r"By\.(ID|NAME|CSS_SELECTOR)\s*,\s*['\"]([^'\"]+)['\"]")
        matches = selector_pattern.findall(script)
        if not matches:
            raise ValueError("Generated script lacks identifiable By.ID/NAME/CSS_SELECTOR references. Please regenerate.")

        missing = []
        for method, selector in matches:
            if method == "ID" and selector not in html_ids:
                missing.append((method, selector))
            elif method == "NAME" and selector not in html_names:
                missing.append((method, selector))
            elif method == "CSS_SELECTOR":
                if selector.startswith("#") and selector[1:] not in html_ids:
                    missing.append((method, selector))
                elif selector.startswith(".") and selector[1:] not in html_classes:
                    missing.append((method, selector))

        if missing:
            detail = ", ".join([f"{method}:{selector}" for method, selector in missing])
            raise ValueError(f"Generated script references selectors not present in checkout.html: {detail}")

    def _get_latest_html_content(self) -> str | None:
        if self.latest_html_content:
            return self.latest_html_content
        if self.latest_html_path and os.path.exists(self.latest_html_path):
            with open(self.latest_html_path, "r", encoding="utf-8") as f:
                self.latest_html_content = f.read()
                return self.latest_html_content
        if os.path.isdir(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                if filename.lower().endswith((".html", ".htm")):
                    html_path = os.path.join(UPLOAD_DIR, filename)
                    with open(html_path, "r", encoding="utf-8") as f:
                        self.latest_html_content = f.read()
                        self.latest_html_path = html_path
                        return self.latest_html_content
        return None

    def _get_html_documents(self) -> List[Document]:
        try:
            html_retriever = self.vector_store.as_retriever(search_kwargs={"k": 3, "filter": {"doc_type": "html"}})
            return html_retriever.invoke("checkout page structure")
        except Exception:
            return []
