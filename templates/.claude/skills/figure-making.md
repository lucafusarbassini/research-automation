# Figure Making Skill

## Technical Requirements
- Format: PDF (vector where possible)
- DPI: 300 for raster elements
- Font: Arial or Helvetica, 8-10pt
- Line width: 0.5-1.5pt
- Colors: Colorblind-friendly palette

## rcParams Template
```python
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.figsize': (3.5, 2.5),  # Single column
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.0,
    'axes.spines.top': False,
    'axes.spines.right': False,
})
```

## Colorblind-Safe Palette
```python
COLORS = {
    'blue': '#0077BB',
    'orange': '#EE7733',
    'green': '#009988',
    'red': '#CC3311',
    'purple': '#AA3377',
    'grey': '#BBBBBB',
}
```

## Sizing
- Single column: 3.5 inches wide
- Double column: 7 inches wide
- Aspect ratio: 4:3 or 16:9

## Export
```python
fig.savefig('figures/fig1.pdf',
            bbox_inches='tight',
            pad_inches=0.02,
            dpi=300)
```
