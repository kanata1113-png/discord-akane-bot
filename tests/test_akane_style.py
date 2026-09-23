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
    assert "モデル" not in conversational
    assert "GPT" not in conversational


def test_fewshot_bank_starts_empty_and_caps_future_examples():
    assert AkaneFewShotBank.MAX_EXAMPLES == 3
    assert AkaneFewShotBank.EXAMPLES == ()
    assert AkaneFewShotBank.select(StyleProfile.CONVERSATIONAL, limit=99) == ()
    assert AkaneFewShotBank.render(StyleProfile.CONVERSATIONAL) == ""


def test_chat_prompt_uses_conversational_profile_without_placeholder_examples():
    prompt = PromptBuilder.chat_system_prompt()

    assert "文体プロファイル: CONVERSATIONAL" in prompt
    assert "一人称は「茜」" in prompt
    assert "【文体例】" not in prompt


def test_translation_uses_transformation_profile_and_preserves_feature_constraint():
    system, user = PromptBuilder.translation_prompt("こんにちは", "English")

    assert "文体プロファイル: TRANSFORMATION" in system
    assert "文体プロファイル: CONVERSATIONAL" not in system
    assert "原文の意味・ニュアンス・口調を可能な限り維持" in system
    assert "余計な解説は不要" in system
    assert "こんにちは" in user


def test_definition_and_summary_use_informational_profile():
    definition_system, _ = PromptBuilder.definition_prompt("API")
    summary_system, _ = PromptBuilder.summary_prompt(["a", "b"])

    assert "文体プロファイル: INFORMATIONAL" in definition_system
    assert "文体プロファイル: INFORMATIONAL" in summary_system
    assert "文体プロファイル: CONVERSATIONAL" not in definition_system
    assert "文体プロファイル: CONVERSATIONAL" not in summary_system


def test_regulation_rules_remain_additive_to_conversational_style():
    prompt = PromptBuilder.chat_system_prompt(regulation_mode=True)

    assert "文体プロファイル: CONVERSATIONAL" in prompt
    assert "【表現の自由・規制関連】" in prompt
    assert "特定の立場へ無条件に同調" in prompt
