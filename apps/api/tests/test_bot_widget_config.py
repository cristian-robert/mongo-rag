"""Tests for the expanded WidgetConfig surface (#87).

Covers: hex validation (RGB + RGBA), HTTPS URL validation, custom-launcher
URL requirement, default values for the new theme tokens.
"""

import pytest
from pydantic import ValidationError

from src.models.bot import (
    BOT_FONTS,
    WidgetConfig,
    WidgetDarkOverrides,
)


@pytest.mark.unit
class TestWidgetConfigDefaults:
    def test_construct_with_no_args_uses_safe_defaults(self) -> None:
        cfg = WidgetConfig()

        # Existing
        assert cfg.primary_color == "#0f172a"
        assert cfg.position == "bottom-right"
        assert cfg.avatar_url is None

        # Color
        assert cfg.color_mode == "light"
        assert cfg.background is None
        assert cfg.dark_overrides is None
        assert cfg.primary_foreground is None

        # Typography
        assert cfg.font_family == "system"
        assert cfg.display_font is None
        assert cfg.base_font_size == "md"

        # Shape & density
        assert cfg.radius == "md"
        assert cfg.density == "comfortable"
        assert cfg.launcher_shape == "circle"
        assert cfg.launcher_size == "md"
        assert cfg.panel_size == "md"

        # Branding & icons
        assert cfg.launcher_icon == "chat"
        assert cfg.launcher_icon_url is None
        assert cfg.show_avatar_in_messages is True
        assert cfg.branding_text is None


@pytest.mark.unit
class TestWidgetConfigColorValidation:
    @pytest.mark.parametrize(
        "value",
        ["#000000", "#FFFFFF", "#0f172a", "#aA1234", "#0f172aff", "#11223344"],
    )
    def test_accepts_rgb_and_rgba_hex(self, value: str) -> None:
        cfg = WidgetConfig(primary_color=value, background=value)
        assert cfg.primary_color == value
        assert cfg.background == value

    @pytest.mark.parametrize(
        "value",
        [
            "0f172a",  # missing #
            "#0f172",  # 5 chars
            "#0f172az",  # invalid char
            "#0f172a1",  # 7 chars
            "#0f172a112",  # 9 chars
            "rgb(0,0,0)",  # not hex
            "#fff",  # shorthand not allowed
        ],
    )
    def test_rejects_bad_hex(self, value: str) -> None:
        with pytest.raises(ValidationError):
            WidgetConfig(primary_color=value)

    def test_accepts_none_for_optional_color(self) -> None:
        cfg = WidgetConfig(background=None, surface=None)
        assert cfg.background is None
        assert cfg.surface is None

    def test_empty_string_treated_as_none(self) -> None:
        cfg = WidgetConfig(background="", surface="")
        assert cfg.background is None
        assert cfg.surface is None


@pytest.mark.unit
class TestWidgetConfigUrlValidation:
    def test_avatar_url_rejects_http(self) -> None:
        with pytest.raises(ValidationError):
            WidgetConfig(avatar_url="http://example.com/a.png")

    def test_avatar_url_accepts_https(self) -> None:
        cfg = WidgetConfig(avatar_url="https://example.com/a.png")
        assert cfg.avatar_url == "https://example.com/a.png"

    def test_launcher_icon_url_rejects_http(self) -> None:
        with pytest.raises(ValidationError):
            WidgetConfig(
                launcher_icon="custom",
                launcher_icon_url="http://example.com/icon.svg",
            )

    def test_launcher_icon_url_accepts_https(self) -> None:
        cfg = WidgetConfig(
            launcher_icon="custom",
            launcher_icon_url="https://example.com/icon.svg",
        )
        assert cfg.launcher_icon_url == "https://example.com/icon.svg"

    def test_url_length_capped(self) -> None:
        long = "https://example.com/" + ("a" * 600)
        with pytest.raises(ValidationError):
            WidgetConfig(avatar_url=long)


@pytest.mark.unit
class TestCustomLauncherIcon:
    def test_custom_requires_url(self) -> None:
        with pytest.raises(ValidationError) as exc:
            WidgetConfig(launcher_icon="custom")
        assert "launcher_icon_url is required" in str(exc.value)

    def test_built_in_icons_do_not_require_url(self) -> None:
        for icon in ("chat", "sparkle", "book", "question"):
            cfg = WidgetConfig(launcher_icon=icon)
            assert cfg.launcher_icon == icon
            assert cfg.launcher_icon_url is None


@pytest.mark.unit
class TestDarkOverrides:
    def test_dark_overrides_optional_fields(self) -> None:
        d = WidgetDarkOverrides(background="#000000", foreground="#ffffff")
        assert d.background == "#000000"
        assert d.foreground == "#ffffff"
        assert d.surface is None

    def test_dark_overrides_validates_hex(self) -> None:
        with pytest.raises(ValidationError):
            WidgetDarkOverrides(background="not-a-hex")

    def test_widget_config_with_dark_overrides_in_light_mode_is_accepted(self) -> None:
        """Dark overrides set in light mode are dead config (logged, not rejected).

        This keeps the API forgiving when a user toggles color_mode back to
        light without clearing their saved dark palette — they shouldn't
        lose their work just because the schema is strict here.
        """
        cfg = WidgetConfig(
            color_mode="light",
            dark_overrides=WidgetDarkOverrides(background="#101010"),
        )
        assert cfg.dark_overrides is not None
        assert cfg.dark_overrides.background == "#101010"


@pytest.mark.unit
class TestBotFonts:
    def test_bot_fonts_includes_system(self) -> None:
        assert "system" in BOT_FONTS

    def test_widget_config_accepts_each_curated_font(self) -> None:
        for font in BOT_FONTS:
            cfg = WidgetConfig(font_family=font)
            assert cfg.font_family == font

    def test_widget_config_rejects_arbitrary_font(self) -> None:
        with pytest.raises(ValidationError):
            WidgetConfig(font_family="comic-sans")  # type: ignore[arg-type]


@pytest.mark.unit
class TestBrandingText:
    def test_branding_text_strips_whitespace(self) -> None:
        cfg = WidgetConfig(branding_text="  Acme Inc  ")
        assert cfg.branding_text == "Acme Inc"

    def test_branding_text_empty_becomes_none(self) -> None:
        cfg = WidgetConfig(branding_text="   ")
        assert cfg.branding_text is None

    def test_branding_text_max_length(self) -> None:
        with pytest.raises(ValidationError):
            WidgetConfig(branding_text="x" * 81)
