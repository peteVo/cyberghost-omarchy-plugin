# Native Omarchy VPN panel

Operate mode for a 13-inch ThinkPad. Preserve the installed Omarchy visual world: `Ui.BarIconButton`, `Ui.Panel`, `Ui.KeyboardPanel`, `Ui.PanelHero`, native buttons, searchable dropdowns, text field, section labels and separators. A 360-unit panel fits to the available screen and scrolls above 550 units. Qt controls own text editing and Tab navigation; Escape closes, and focused controls scroll into view.

Typography uses `Style.font`; spacing, borders, focus, hover and animation come from the shell's controls and tokens. Text uses the popup theme palette in both light and dark themes. CyberGhost yellow is limited to the connected CG mark. All external content is plain text. Connection state, selected next location and last public-IP lookup are separate concepts.

The main action stays disabled until a backend can confirm an actionable state. Loading, unknown, dependency, profile, authorization, location-empty and retry states are explicit. Country/city search uses the native searchable dropdown and exposes only discovered options. Session settings are labelled; unimplemented security/reconnect/server features are described truthfully rather than displayed as working controls.

Source/API and accessibility paths were reviewed using Impeccable. Qt lint resolves installed shell imports but reports dynamic-property warnings. No screenshot was captured and no visual approval is claimed: the managed session cannot reach the host desktop. Contrast, ThinkPad scaling, focus rings, keyboard traversal, dropdown placement, clicks and panel lifecycle remain to be checked once in the existing Omarchy shell, followed by one bounded correction/confirmation pass if needed.
