from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


class VectorStore:

    def build(self, docs):

        embeddings = OpenAIEmbeddings()

        db = Chroma.from_documents(
            docs,
            embeddings,
            persist_directory="./data/chroma"
        )

        return db