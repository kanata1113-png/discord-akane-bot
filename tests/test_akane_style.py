from services.akane_fewshot_bank import AkaneFewShotBank
from services.akane_style_contract import AkaneStyleContract, StyleProfile
from services.prompt_builder import PromptBuilder


def test_style_contract_profiles_are_explicit_and_model_independent():
    conversational = AkaneStyleContract.render(StyleProfile.CONVERSATIONAL)
    informational = AkaneStyleContract.render(StyleProfile.INFORMATIONAL)
    transformation = AkaneStyleContract.render(StyleProfile.TRANSFORMATION)

    assert "CONVERSATIONAL" in conversational
    assert "INFORMATIONAL" in informational
    assert "TRANSFORMATION" in transformation
    assert "GPT" not in conversational
    assert "`インラインコード` > __下線__ > **太字**" in conversational
    assert "不要な空白行を入れず" in conversational


def test_fewshot_bank_contains_only_minimal_three_examples_and_caps_selection():
    assert AkaneFewShotBank.MAX_EXAMPLES == 3
    assert len(AkaneFewShotBank.EXAMPLES) == 3

    conversational = AkaneFewShotBank.select(
        StyleProfile.CONVERSATIONAL,
        feature="chat",
        limit=99,
    )
    informational = AkaneFewShotBank.select(
        StyleProfile.INFORMATIONAL,
        feature="summary",
        limit=99,
    )
    transformation = AkaneFewShotBank.select(
        StyleProfile.TRANSFORMATION,
        feature="translation",
        limit=99,
    )

    assert len(conversational) == 1
    assert len(informational) == 1
    assert len(transformation) == 1
    assert conversational[0].key == "conversational_api"
    assert informational[0].key == "informational_local_vs_cloud"
    assert transformation[0].key == "transformation_translation"


def test_fewshot_render_is_compact_and_does_not_insert_blank_line_between_roles():
    prompt = AkaneFewShotBank.render(
        StyleProfile.CONVERSATIONAL,
        feature="chat",
    )

    assert "User:\nAPIって何？\nAssistant:" in prompt
    assert "User:\nAPIって何？\n\nAssistant:" not in prompt
    assert "サービス同士の受付窓口" in prompt


def test_chat_prompt_uses_conversational_profile_and_canonical_example():
    prompt = PromptBuilder.chat_system_prompt()

    assert "文体プロファイル: CONVERSATIONAL" in prompt
    assert "一人称は「茜」" in prompt
    assert "【文体例】" in prompt
    assert "APIって何？" in prompt


def test_response_style_has_short_and_longform_heading_rules():
    prompt = PromptBuilder.response_style_prompt(None, target_characters=1200)

    assert "1000文字未満" in prompt
    assert "1000文字以上" in prompt
    assert "`##` を主要見出し" in prompt
    assert "`###` は明確な下位区分" in prompt
    assert "`#` と `####` 以下は使わない" in prompt
    assert "不要な空白行を入れず" in prompt


def test_translation_uses_transformation_profile_and_preserves_feature_constraint():
    system, user = PromptBuilder.translation_prompt("こんにちは", "English")

    assert "文体プロファイル: TRANSFORMATION" in system
    assert "文体プロファイル: CONVERSATIONAL" not in system
    assert "原文の意味・ニュアンス・口調を可能な限り維持" in system
    assert "余計な解説は不要" in system
    assert "Freedom of expression is a foundation of democracy." in system
    assert "こんにちは" in user


def test_definition_and_summary_use_informational_profile_and_shared_style_anchor():
    definition_system, _ = PromptBuilder.definition_prompt("API")
    summary_system, _ = PromptBuilder.summary_prompt(["a", "b"])

    assert "文体プロファイル: INFORMATIONAL" in definition_system
    assert "文体プロファイル: INFORMATIONAL" in summary_system
    assert "文体プロファイル: CONVERSATIONAL" not in definition_system
    assert "文体プロファイル: CONVERSATIONAL" not in summary_system
    assert "ローカルAIとクラウドAIの違い" in definition_system
    assert "ローカルAIとクラウドAIの違い" in summary_system


def test_regulation_rules_remain_additive_to_conversational_style():
    prompt = PromptBuilder.chat_system_prompt(regulation_mode=True)

    assert "文体プロファイル: CONVERSATIONAL" in prompt
    assert "【表現の自由・規制関連】" in prompt
    assert "特定の立場へ無条件に同調" in prompt
