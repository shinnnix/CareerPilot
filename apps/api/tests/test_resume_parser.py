from app.domains.resumes.parser import parse_resume_content, resume_corpus
from app.domains.resumes.suggestions import rewrite_weak_verb


def test_rewrite_weak_verb_keeps_facts_and_is_idempotent() -> None:
    assert rewrite_weak_verb("参与需求分析，完成订单模块的接口开发。") == (
        "参与并交付 需求分析，完成订单模块的接口开发。"
    )
    assert rewrite_weak_verb("负责订单接口开发") == "主导 订单接口开发"
    # Re-generating after applying the rewrite must not stack verbs.
    assert rewrite_weak_verb("参与并交付 需求分析，完成订单模块的接口开发。") is None
    assert rewrite_weak_verb("使用 FastAPI 提供可观测接口") is None
    assert rewrite_weak_verb("参与") is None


def test_section_aliases_are_grouped_into_core_sections() -> None:
    parsed = parse_resume_content(
        raw_text=(
            "李四\n13800000000\nlisi@example.com\n\n"
            "教育背景\n某大学 | 软件工程 · 本科 | 2018.09 - 2022.06\n"
            "- 主修课程：数据库、编译原理\n\n"
            "工作经历\n某公司 | 后端开发实习生 | 2022.07 - 2022.12\n"
            "- 负责订单接口开发\n\n"
            "技能清单\n- Python、FastAPI\n\n"
            "个人总结\n做事细致，擅长用测试保护重构。"
        ),
        display_name="李四简历",
    )

    keys = [section.key.value for section in parsed.sections]
    assert keys == ["education", "experience", "project", "skill", "summary"]
    assert parsed.head.name == "李四"
    assert parsed.head.phone == "13800000000"
    assert any("项目经历" in warning for warning in parsed.warnings)
    experience = next(section for section in parsed.sections if section.key.value == "experience")
    assert experience.entries[0].title == "某公司"
    assert experience.entries[0].period == "2022.07-2022.12"


def test_unrecognized_heading_is_kept_as_other_section() -> None:
    parsed = parse_resume_content(
        raw_text=(
            "王五\n\n教育经历\n某大学 | 数学 · 本科 | 2019.09 - 2023.06\n\n"
            "获奖情况\n- 校级一等奖学金\n"
        ),
        display_name="王五简历",
    )

    other = next(section for section in parsed.sections if section.key.value == "other")
    assert other.title == "获奖情况"
    assert other.entries[0].bullets == ["校级一等奖学金"]


def test_resume_corpus_reads_user_edited_structure() -> None:
    parsed = parse_resume_content(
        raw_text="张三\n\n项目经历\n项目 A | 技术栈：Python\n- 使用 FastAPI 提供接口\n",
        display_name="张三简历",
    )
    project = next(section for section in parsed.sections if section.key.value == "project")
    project.entries[0].bullets[0] = "使用 FastAPI 提供可观测接口"

    corpus = resume_corpus(parsed.head, parsed.sections)

    assert "使用 FastAPI 提供可观测接口" in corpus
    assert "张三" in corpus


def test_paragraph_lines_stay_in_one_summary_entry() -> None:
    parsed = parse_resume_content(
        raw_text=(
            "赵六\n\n自我评价\n第一段自我评价内容。\n\n"
            "第二段说明自己的工程习惯与协作方式。\n"
        ),
        display_name="赵六简历",
    )

    summary = next(section for section in parsed.sections if section.key.value == "summary")
    assert [entry.title for entry in summary.entries] == [
        "第一段自我评价内容。",
        "第二段说明自己的工程习惯与协作方式。",
    ]
    assert summary.entries[0].bullets == []
