from app.domains.documents.model import DocumentType
from app.domains.documents.parser import hash_text, parse_document

SAMPLE_JD = """AI 应用开发实习生
公司：星河智能
工作地点：上海

岗位职责：
- 使用 FastAPI 开发 AI 应用后端
- 参与 RAG 私人知识库设计

任职要求：
- 熟悉 Python 和 PostgreSQL
- 每周至少实习四天

加分项：
- 了解 Vue 3、LangChain 或 Docker
"""


def test_parser_extracts_sections_skills_and_contextualized_chunks() -> None:
    result = parse_document(
        raw_text=SAMPLE_JD,
        document_type=DocumentType.job_description,
        display_name="星河智能 AI 实习",
    )

    assert result.extracted_data.company_name == "星河智能"
    assert result.extracted_data.city == "上海"
    assert {"fastapi", "rag", "python", "postgresql", "vue"}.issubset(result.extracted_data.skills)
    assert "岗位职责" in result.extracted_data.section_titles
    requirement_chunks = [chunk for chunk in result.chunks if chunk.chunk_type == "requirement"]
    assert len(requirement_chunks) == 2
    assert requirement_chunks[0].section_path == ["星河智能 AI 实习", "任职要求"]
    assert "章节：任职要求" in requirement_chunks[0].contextualized_content
    assert result.confidence >= 0.8


def test_hash_is_stable_after_newline_and_trailing_space_normalization() -> None:
    first = "项目经历：\r\n使用 FastAPI 构建后端。   \r\n"
    second = "项目经历：\n使用 FastAPI 构建后端。"

    assert hash_text(first) == hash_text(second)


def test_long_section_is_split_with_bounded_chunk_size() -> None:
    text = "项目经历：\n" + "使用 Python 和 FastAPI 完成系统开发。" * 80

    result = parse_document(
        raw_text=text,
        document_type=DocumentType.resume,
        display_name="测试简历",
    )

    assert len(result.chunks) > 1
    assert all(chunk.char_count <= 600 for chunk in result.chunks)


def test_short_skill_alias_does_not_match_inside_another_word() -> None:
    result = parse_document(
        raw_text="项目经历：\n负责 storage service 的接口设计与自动化测试工作。",
        document_type=DocumentType.resume,
        display_name="边界测试简历",
    )

    assert "rag" not in result.extracted_data.skills
