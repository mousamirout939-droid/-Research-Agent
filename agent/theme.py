"""
Custom Gradio theme: "Night Margin" -- a dark, ink-on-paper research theme.

Design language: an academic paper read at night, annotated in highlighter
amber, with citation footnotes and a live margin note showing the agent's
pipeline. Serif for headlines (Lora), clean sans for UI chrome (Inter),
monospace for citation tags / scores / metadata (JetBrains Mono).

We intentionally set the *light* and *dark* variant of every variable to
the same dark value below. Gradio normally switches between the two based
on the visitor's OS preference; setting both identically means the app
looks the same (dark) regardless of that preference, which is what was
asked for here.
"""
from __future__ import annotations

import gradio as gr
from gradio.themes.utils import colors, sizes

# ---- palette -------------------------------------------------------------
BG = "#0B0F14"          # canvas -- ink-blue near-black
SURFACE = "#121822"     # panel surface
SURFACE_RAISED = "#182030"
BORDER = "#232C3A"
INK = "#E7EAEE"         # primary text
MUTED = "#8B96A5"       # secondary text
HIGHLIGHTER = "#F2B84B"  # primary accent -- highlighter amber
VERIFIED = "#34D1A6"    # teal -- supported / complete
PARTIAL = "#F2B84B"     # amber -- partially supported
UNSUPPORTED = "#EF6461"  # muted coral -- unsupported / uncited / error

_highlighter_scale = colors.Color(
    name="highlighter",
    c50="#FEF6E7", c100="#FCE9C3", c200="#F9DC9E", c300="#F6CE79",
    c400="#F4C158", c500=HIGHLIGHTER, c600="#D49A2F", c700="#A8761F",
    c800="#7C5614", c900="#503509", c950="#2E1E04",
)

_neutral_scale = colors.Color(
    name="ink_neutral",
    c50="#E7EAEE", c100="#C9CFD8", c200="#A9B2BF", c300="#8B96A5",
    c400="#6B7585", c500="#4C5566", c600="#363D4A", c700="#262C37",
    c800=SURFACE, c900=BG, c950="#06080B",
)


class NightMarginTheme(gr.themes.Base):
    """A dark research/annotation themed Gradio theme."""

    def __init__(self):
        super().__init__(
            primary_hue=_highlighter_scale,
            secondary_hue=colors.teal,
            neutral_hue=_neutral_scale,
            spacing_size=sizes.spacing_md,
            radius_size=sizes.radius_md,
            text_size=sizes.text_md,
            font=(gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"),
            font_mono=(gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "Consolas", "monospace"),
        )
        self.set(
            # -- canvas / body --------------------------------------------------
            body_background_fill=BG,
            body_background_fill_dark=BG,
            body_text_color=INK,
            body_text_color_dark=INK,
            body_text_color_subdued=MUTED,
            body_text_color_subdued_dark=MUTED,
            color_accent=HIGHLIGHTER,
            color_accent_soft="#3A2E16",
            color_accent_soft_dark="#3A2E16",
            link_text_color=HIGHLIGHTER,
            link_text_color_dark=HIGHLIGHTER,
            link_text_color_hover=VERIFIED,
            link_text_color_hover_dark=VERIFIED,
            # -- generic blocks/panels ------------------------------------------
            background_fill_primary=SURFACE,
            background_fill_primary_dark=SURFACE,
            background_fill_secondary=SURFACE_RAISED,
            background_fill_secondary_dark=SURFACE_RAISED,
            border_color_primary=BORDER,
            border_color_primary_dark=BORDER,
            border_color_accent=HIGHLIGHTER,
            border_color_accent_dark=HIGHLIGHTER,
            block_background_fill=SURFACE,
            block_background_fill_dark=SURFACE,
            block_border_color=BORDER,
            block_border_color_dark=BORDER,
            block_label_background_fill=SURFACE_RAISED,
            block_label_background_fill_dark=SURFACE_RAISED,
            block_label_text_color=MUTED,
            block_label_text_color_dark=MUTED,
            block_title_text_color=INK,
            block_title_text_color_dark=INK,
            block_info_text_color=MUTED,
            block_info_text_color_dark=MUTED,
            panel_background_fill=SURFACE,
            panel_background_fill_dark=SURFACE,
            panel_border_color=BORDER,
            panel_border_color_dark=BORDER,
            # -- inputs -----------------------------------------------------------
            input_background_fill=SURFACE_RAISED,
            input_background_fill_dark=SURFACE_RAISED,
            input_background_fill_focus=SURFACE_RAISED,
            input_background_fill_focus_dark=SURFACE_RAISED,
            input_border_color=BORDER,
            input_border_color_dark=BORDER,
            input_border_color_focus=HIGHLIGHTER,
            input_border_color_focus_dark=HIGHLIGHTER,
            input_placeholder_color=MUTED,
            input_placeholder_color_dark=MUTED,
            # -- buttons -----------------------------------------------------------
            button_primary_background_fill=HIGHLIGHTER,
            button_primary_background_fill_dark=HIGHLIGHTER,
            button_primary_background_fill_hover="#F6CE79",
            button_primary_background_fill_hover_dark="#F6CE79",
            button_primary_text_color=BG,
            button_primary_text_color_dark=BG,
            button_primary_border_color=HIGHLIGHTER,
            button_primary_border_color_dark=HIGHLIGHTER,
            button_secondary_background_fill=SURFACE_RAISED,
            button_secondary_background_fill_dark=SURFACE_RAISED,
            button_secondary_background_fill_hover=BORDER,
            button_secondary_background_fill_hover_dark=BORDER,
            button_secondary_text_color=INK,
            button_secondary_text_color_dark=INK,
            button_secondary_border_color=BORDER,
            button_secondary_border_color_dark=BORDER,
            # -- misc -----------------------------------------------------------
            shadow_drop="0 1px 2px rgba(0,0,0,0.4)",
            slider_color=HIGHLIGHTER,
            slider_color_dark=HIGHLIGHTER,
            checkbox_background_color=SURFACE_RAISED,
            checkbox_background_color_dark=SURFACE_RAISED,
            checkbox_background_color_selected=HIGHLIGHTER,
            checkbox_background_color_selected_dark=HIGHLIGHTER,
            checkbox_border_color=BORDER,
            checkbox_border_color_dark=BORDER,
            checkbox_label_text_color=INK,
            checkbox_label_text_color_dark=INK,
            error_background_fill="#2A1414",
            error_background_fill_dark="#2A1414",
            error_border_color=UNSUPPORTED,
            error_border_color_dark=UNSUPPORTED,
            error_text_color=UNSUPPORTED,
            error_text_color_dark=UNSUPPORTED,
            code_background_fill=SURFACE_RAISED,
            code_background_fill_dark=SURFACE_RAISED,
        )


night_margin_theme = NightMarginTheme()
