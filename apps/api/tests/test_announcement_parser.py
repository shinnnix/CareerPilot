from datetime import date

from app.domains.jobs.announcement_parser import parse_announcement


def test_parses_bracketed_company_and_keywords() -> None:
    text = (
        "【恒远集团】2028届春季校园招聘\n"
        "恒远集团面向高校招聘研发人才。\n"
        "招聘岗位：机械设计工程师、电气工程师\n"
        "工作地点：苏州、无锡\n"
        "截止时间：招满为止\n"
    )

    parsed = parse_announcement(text)

    assert parsed.company_name == "恒远集团"
    assert parsed.recruitment_type == "春招"
    assert parsed.target_cohort == "2028届"
    assert parsed.locations == ["苏州", "无锡"]
    assert parsed.positions == ["机械设计工程师", "电气工程师"]
    assert parsed.deadline_text == "招满为止"
    assert parsed.deadline_at is None


def test_falls_back_to_source_name_and_extracts_apply_method() -> None:
    text = (
        "招聘公告\n"
        "本次招聘面向 2027 届毕业生。\n"
        "岗位：数据分析、产品运营\n"
        "请将简历投递至 hr@example.com 或访问 https://jobs.example.com/apply\n"
    )

    parsed = parse_announcement(text, source_name="某某科技公司")

    assert parsed.company_name == "某某科技公司"
    assert parsed.target_cohort == "2027届"
    assert parsed.positions == ["数据分析", "产品运营"]
    assert parsed.apply_method["emails"] == ["hr@example.com"]
    assert parsed.apply_method["links"] == ["https://jobs.example.com/apply"]


def test_parses_month_day_deadline_using_reference_year() -> None:
    text = (
        "【云帆数据】校园招聘\n"
        "招聘岗位：后端开发\n"
        "报名截止：3月15日\n"
    )

    parsed = parse_announcement(text, today=date(2027, 1, 5))

    assert parsed.deadline_text == "2027-03-15"
    assert parsed.deadline_at is not None
    assert parsed.deadline_at.year == 2027


def test_never_raises_on_noisy_input() -> None:
    parsed = parse_announcement("随便一段没有结构的中文文本，用于验证规则解析不会抛错。" * 2)

    assert parsed.title is not None
    assert parsed.positions == []
    assert parsed.confidence["positions"] == "low"
