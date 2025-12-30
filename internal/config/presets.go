package config

func GetBuiltinThemes() map[string]Theme {
	return map[string]Theme{
		"gruvbox-dark":         GruvboxDark(),
		"gruvbox-light":        GruvboxLight(),
		"catppuccin-frappe":    CatppuccinFrappe(),
		"catppuccin-macchiato": CatppuccinMacchiato(),
		"tokyo-night":          TokyoNight(),
		"tokyo-night-storm":    TokyoNightStorm(),
		"nord":                 Nord(),
		"dracula":              Dracula(),
	}
}

func GruvboxDark() Theme {
	return Theme{
		Name: "gruvbox-dark",
		Colors: ColorPalette{
			Background:           "#282828",
			Foreground:           "#ebdbb2",
			Primary:              "#fe8019",
			Secondary:            "#d3869b",
			Accent:               "#fabd2f",
			Success:              "#98971a",
			Warning:              "#d79921",
			Error:                "#cc241d",
			Info:                 "#458588",
			Border:               "#3c3836",
			Muted:                "#928374",
			Disabled:             "#665c54",
			StatusbarBackground:  "#1d2021",
			LauncherBackground:   "#1d2021",
			LockscreenBackground: "#1d2021",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func GruvboxLight() Theme {
	return Theme{
		Name: "gruvbox-light",
		Colors: ColorPalette{
			Background:           "#fbf1c7",
			Foreground:           "#3c3836",
			Primary:              "#d65d0e",
			Secondary:            "#b16286",
			Accent:               "#d5c4a1",
			Success:              "#98971a",
			Warning:              "#b57614",
			Error:                "#cc241d",
			Info:                 "#458588",
			Border:               "#ebdbb2",
			Muted:                "#7c6f64",
			Disabled:             "#a89984",
			StatusbarBackground:  "#f2e5bc",
			LauncherBackground:   "#f2e5bc",
			LockscreenBackground: "#f2e5bc",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func CatppuccinFrappe() Theme {
	return Theme{
		Name: "catppuccin-frappe",
		Colors: ColorPalette{
			Background:           "#303446",
			Foreground:           "#c6d0f5",
			Primary:              "#8caaee",
			Secondary:            "#ca9ee6",
			Accent:               "#ef9f76",
			Success:              "#a6d189",
			Warning:              "#e5c890",
			Error:                "#e78284",
			Info:                 "#85c1dc",
			Border:               "#414559",
			Muted:                "#737994",
			Disabled:             "#626880",
			StatusbarBackground:  "#292c3c",
			LauncherBackground:   "#24273a",
			LockscreenBackground: "#24273a",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func CatppuccinMacchiato() Theme {
	return Theme{
		Name: "catppuccin-macchiato",
		Colors: ColorPalette{
			Background:           "#24273a",
			Foreground:           "#cad3f5",
			Primary:              "#8aadf4",
			Secondary:            "#c6a0f6",
			Accent:               "#f5a97f",
			Success:              "#a6da95",
			Warning:              "#eed49f",
			Error:                "#ed8796",
			Info:                 "#91d7e3",
			Border:               "#363a4f",
			Muted:                "#6e738d",
			Disabled:             "#5b6078",
			StatusbarBackground:  "#1e2030",
			LauncherBackground:   "#181926",
			LockscreenBackground: "#181926",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func TokyoNight() Theme {
	return Theme{
		Name: "tokyo-night",
		Colors: ColorPalette{
			Background:           "#1a1b26",
			Foreground:           "#c0caf5",
			Primary:              "#7aa2f7",
			Secondary:            "#bb9af7",
			Accent:               "#e0af68",
			Success:              "#9ece6a",
			Warning:              "#e0af68",
			Error:                "#f7768e",
			Info:                 "#7dcfff",
			Border:               "#414868",
			Muted:                "#565f89",
			Disabled:             "#414868",
			StatusbarBackground:  "#16161e",
			LauncherBackground:   "#16161e",
			LockscreenBackground: "#16161e",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func TokyoNightStorm() Theme {
	return Theme{
		Name: "tokyo-night-storm",
		Colors: ColorPalette{
			Background:           "#24283b",
			Foreground:           "#c0caf5",
			Primary:              "#7aa2f7",
			Secondary:            "#bb9af7",
			Accent:               "#e0af68",
			Success:              "#9ece6a",
			Warning:              "#e0af68",
			Error:                "#f7768e",
			Info:                 "#7dcfff",
			Border:               "#414868",
			Muted:                "#565f89",
			Disabled:             "#565f89",
			StatusbarBackground:  "#1f2335",
			LauncherBackground:   "#1a1b26",
			LockscreenBackground: "#1a1b26",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func Nord() Theme {
	return Theme{
		Name: "nord",
		Colors: ColorPalette{
			Background:           "#2e3440",
			Foreground:           "#eceff4",
			Primary:              "#88c0d0",
			Secondary:            "#b48ead",
			Accent:               "#ebcb8b",
			Success:              "#a3be8c",
			Warning:              "#ebcb8b",
			Error:                "#bf616a",
			Info:                 "#81a1c1",
			Border:               "#3b4252",
			Muted:                "#d8dee9",
			Disabled:             "#4c566a",
			StatusbarBackground:  "#272c36",
			LauncherBackground:   "#272c36",
			LockscreenBackground: "#272c36",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}

func Dracula() Theme {
	return Theme{
		Name: "dracula",
		Colors: ColorPalette{
			Background:           "#282a36",
			Foreground:           "#f8f8f2",
			Primary:              "#bd93f9",
			Secondary:            "#ff79c6",
			Accent:               "#f1fa8c",
			Success:              "#50fa7b",
			Warning:              "#ffb86c",
			Error:                "#ff5555",
			Info:                 "#8be9fd",
			Border:               "#44475a",
			Muted:                "#6272a4",
			Disabled:             "#44475a",
			StatusbarBackground:  "#21222c",
			LauncherBackground:   "#1e1f29",
			LockscreenBackground: "#1e1f29",
		},
		Typography:   DefaultTypography(),
		Spacing:      DefaultSpacing(),
		BorderRadius: DefaultBorderRadius(),
	}
}
