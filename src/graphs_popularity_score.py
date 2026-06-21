import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# 1. Chargement et filtrage des données
df = pd.read_csv("results/popularity_scores.csv", sep=";")
if len(df.columns) == 4:
    df = df.iloc[:, 1:]
df.columns = ["event_type", "month", "average_popularity_score"]

# --- FILTRAGE : On exclut le type 'miscellaneous' ---
df = df[df["event_type"] != "miscellaneous"]

# 2. Préparation de la matrice pour la heatmap
pivot_df = df.pivot(
    index="event_type", columns="month", values="average_popularity_score"
)
pivot_df = pivot_df.reindex(columns=range(1, 13))

months_fr = [
    "Jan",
    "Fév",
    "Mar",
    "Avr",
    "Mai",
    "Juin",
    "Juil",
    "Aoû",
    "Sep",
    "Oct",
    "Nov",
    "Déc",
]

# 3. Configuration du style Seaborn
sns.set_theme(style="whitegrid")
plt.figure(figsize=(12, 5), dpi=100)  # Hauteur légèrement réduite (5 au lieu de 6) car il y a une ligne de moins

# 4. Génération de la Heatmap
ax = sns.heatmap(
    pivot_df,
    annot=True,
    fmt=".1f",
    cmap="YlGnBu",
    linewidths=0.5,
    cbar_kws={"label": "Score de popularité moyen"},
    xticklabels=months_fr,
)

# 5. Personnalisation des titres et axes
plt.title(
    "Évolution de la popularité des événements selon le mois",
    fontsize=16,
    fontweight="bold",
    pad=20,
)
plt.xlabel("Mois de l'année", fontsize=12, labelpad=10)
plt.ylabel("Type d'événement", fontsize=12, labelpad=10)

plt.xticks(rotation=0)
plt.yticks(rotation=0)
plt.tight_layout()

# 6. Sauvegarde
plt.savefig("results/popularity_heatmap.png", dpi=300, bbox_inches="tight")
plt.close()

print(
    "Graphique Heatmap (sans 'miscellaneous') enregistré dans 'results/popularity_heatmap.png' !"
)

# 1. Chargement et filtrage des données
df = pd.read_csv("results/popularity_scores.csv", sep=";")
if len(df.columns) == 4:
    df = df.iloc[:, 1:]
df.columns = ["event_type", "month", "average_popularity_score"]

# --- FILTRAGE : On exclut le type 'miscellaneous' ---
df = df[df["event_type"] != "miscellaneous"]

months_fr = [
    "Jan",
    "Fév",
    "Mar",
    "Avr",
    "Mai",
    "Juin",
    "Juil",
    "Aoû",
    "Sep",
    "Oct",
    "Nov",
    "Déc",
]

# 2. Configuration du style
sns.set_theme(style="whitegrid")
plt.figure(figsize=(12, 6), dpi=100)

# 3. Création du Line Plot
ax = sns.lineplot(
    data=df,
    x="month",
    y="average_popularity_score",
    hue="event_type",
    style="event_type",
    markers=True,
    markersize=8,
    linewidth=2.5,
    palette="Set2",
)

# 4. Personnalisation des axes et légendes
plt.title(
    "Tendances mensuelles de la popularité par type d'événement",
    fontsize=16,
    fontweight="bold",
    pad=20,
)
plt.xlabel("Mois de l'année", fontsize=12, labelpad=10)
plt.ylabel("Score de popularité moyen", fontsize=12, labelpad=10)

plt.xticks(ticks=range(1, 13), labels=months_fr)
plt.legend(title="Types d'événements", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# 5. Sauvegarde de l'image
plt.savefig("results/popularity_trends.png", dpi=300, bbox_inches="tight")
plt.close()

print(
    "Graphique en lignes (sans 'miscellaneous') enregistré dans 'results/popularity_trends.png' !"
)