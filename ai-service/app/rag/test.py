def main():
    from app.rag.service import RAGService

    rag = RAGService()

    response = rag.chat(
        question="who is alchemist?",
        model="gpt-4o-mini",
        temperature=0.2,
        top_k=10,
        top_p=0.9,
        max_tokens=500,
    )

    print(response.to_dict())


if __name__ == "__main__":
    main()
