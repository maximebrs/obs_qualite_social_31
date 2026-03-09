import os
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# FONCTIONS

@st.cache_data
def load_geo_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "data_social_31_geo.geojson")
    if not os.path.exists(file_path):
        st.error(f"Fichier GeoJSON introuvable : {file_path}")
        return None
    return gpd.read_file(file_path)

def get_dpe_label(score):
        lettre = score_to_lettre.get(int(round(score)), "?")
        return f"{lettre} ({score:.1f})"

def get_morpho(val):
    v = str(val).lower()
    if "maison" in v: return "Individuel"
    if "appartement" in v or "immeuble" in v: return "Collectif"
    return "Autre"

# 1. CONFIGURATION DE LA PAGE
st.set_page_config(
    page_title="Obs. Logement Social 31",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. CSS PERSONNALISÉ = DASHBOARD ONE-SCREEN
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.8rem;
        }
        hr {
            margin-top: 0rem;
            margin-bottom: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

# 3. CHARGEMENT DES DONNÉES GEOJSON

gdf = load_geo_data()
if gdf is None:
    st.error("Impossible de continuer : le fichier GeoJSON est manquant.")
    st.stop()

# 4. DICTIONNAIRE BANATIC
noms_epci = {
    "243100518": "Toulouse Métropole",
    "200034957": "CC du Frontonnais",
    "243100773": "CC Val'Aïgo",
    "200071298": "CC des Terres du Lauragais",
    "200072635": "CC Pyrénées Haut Garonnaises",
    "200068641": "CA Le Muretain Agglo",
    "200073146": "CC Cagire Garonne Salat",
    "200066819": "CC du Volvestre",
    "243100567": "CC Aux sources du Canal du Midi",
    "243100633": "CA du Sicoval",
    "200072643": "CC Coeur et Coteaux du Comminges",
    "243100781": "Le Grand Ouest Toulousain agglomération",
    "200068815": "CC Coeur de Garonne",
    "200071314": "CC des Hauts-Tolosans",
    "200068807": "CC du Bassin Auterivain Haut-Garonnais",
    "243100815": "CC des Coteaux Bellevue",
    "243100732": "CC des Coteaux du Girou"
}
gdf['nom_epci'] = gdf['code_epci_insee'].astype(str).map(noms_epci)

# Gestion des DPE
color_map = {
    'A': '#008055', 'B': '#33cc33', 'C': '#cccc00', 
    'D': '#ffcc00', 'E': '#ff9933', 'F': '#ff6600', 'G': '#cc3300',
    'Non renseigné': '#d3d3d3'
}
dpe_score_map = {'A': 7, 'B': 6, 'C': 5, 'D': 4, 'E': 3, 'F': 2, 'G': 1}
gdf['dpe_score_num'] = pd.to_numeric(gdf['classe_ener_principale'].map(dpe_score_map), errors='coerce')
score_to_lettre = {v: k for k, v in dpe_score_map.items()}

# --- ÉTAPE 1 : HEADER ---
st.title("🏙️ Qualité énergétique du Parc Locatif Social 31")

col_gauche, col_droite = st.columns([1, 2])

with col_gauche:
    # 1. FILTRE DE SÉLECTION DU TERRITOIRE 
    liste_noms = sorted(list(noms_epci.values()))
    choix = st.selectbox("Choisir un territoire :", ["Toute la Haute-Garonne"] + liste_noms)
    if choix == "Toute la Haute-Garonne":
        gdf_filtered = gdf
    else:
        code_insee = [k for k, v in noms_epci.items() if v == choix][0]
        # On s'assure que la comparaison se fait sur des chaînes de caractères
        gdf_filtered = gdf[gdf['code_epci_insee'].astype(str) == str(code_insee)]

    # 2. KPIs
    kpi1, kpi2, kpi3 = st.columns(3, vertical_alignment="bottom")

    with kpi1:
        total_log = int(gdf_filtered['nb_log'].sum())
        st.metric("Volume du Parc Locatif Social", f"{total_log:,}".replace(',', ' '))

    with kpi2:
        score_moyen = (gdf_filtered['dpe_score_num'] * gdf_filtered['nb_log']).sum() / total_log if total_log > 0 else 0
        score_label = get_dpe_label(score_moyen)
        st.metric(
            label="Score DPE Moyen",
            value=score_label,
            help="Moyenne pondérée des étiquettes DPE (A=7, G=1).\n\n Plus le score est élevé, plus le parc est performant."
        )

    with kpi3:
        passoires_codes = ['E', 'F', 'G']
        nb_passoires = gdf_filtered[gdf_filtered['classe_ener_principale'].isin(passoires_codes)]['nb_log'].sum()
        pct_passoires = (nb_passoires / total_log * 100) if total_log > 0 else 0
        st.metric("Taux de Passoires", f"{pct_passoires:.1f} %", 
                  help="Les classes E, F et G sont considérées comme des passoires thermiques.")

    # 3. CARTE CONTEXTE

    # Légende
    poids_leg = [1, 1, 1, 1, 1, 1, 1, 4]
    cols_leg = st.columns(poids_leg)
    for i, (classe, couleur) in enumerate(color_map.items()):
        with cols_leg[i]:
            st.markdown(
                f'''
                <div style="display: flex; align-items: center; gap: 4px; white-space: nowrap;">
                    <div style="width: 14px; height: 14px; background-color: {couleur}; 
                                border-radius: 3px; border: 1px solid #555; flex-shrink: 0;"></div>
                    <span style="font-size: 0.85rem; font-weight: bold;">{classe}</span>
                </div>
                ''',
                unsafe_allow_html=True
            )

    with st.spinner("Génération de la carte et analyse statistique des données..."):
        # Définition du centre et du zoom
        if choix == "Toute la Haute-Garonne":
            center, zoom = [43.27274346158933, 1.1799586081287927], 10
            data_to_map = gdf.dropna(subset=['lat', 'lon'])
        else:
            center = [gdf_filtered['lat'].mean(), gdf_filtered['lon'].mean()]
            zoom = 11
            data_to_map = gdf_filtered.dropna(subset=['lat', 'lon'])

        # Création de la carte Folium (fond clair pour faire ressortir les points)
        m = folium.Map(location=center, zoom_start=zoom, tiles=None)

        # Ajout des fonds de plan (Contrôleur de couches)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google',
            name='Google Satellite', control=True
        ).add_to(m)
        folium.TileLayer('cartodbpositron', name="Plan Clair", control=True).add_to(m)

        try:
            if choix == "Toute la Haute-Garonne":
                # 1. Préparation de l'URL
                url_dept = "https://geo.api.gouv.fr/epcis?codeDepartement=31&format=geojson&geometry=contour"
                try:
                    gdf_zoom = gpd.read_file(url_dept)
                    b = gdf_zoom.total_bounds
                    m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
                except:
                    pass
                # 3. Code d'affichage des contours EPCI
                folium.GeoJson(
                    url_dept, name="Limites EPCI",
                    style_function=lambda x: {'fillColor': 'none', 'color': 'black', 'weight': 1, 'opacity': 0.5}
                ).add_to(m)
            else:
                # 1. Préparation des URLs
                url_contour = f"https://geo.api.gouv.fr/epcis/{code_insee}?format=geojson&geometry=contour"
                url_communes = f"https://geo.api.gouv.fr/epcis/{code_insee}/communes?format=geojson&geometry=contour"
                # 2. Calcul du zoom sur l'EPCI sélectionné
                try:
                    gdf_zoom = gpd.read_file(url_contour)
                    b = gdf_zoom.total_bounds
                    m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
                except:
                    pass 
                # 3. Code d'affichage des contours
                folium.GeoJson(
                    url_contour,
                    name="Contour EPCI",
                    style_function=lambda x: {'fillColor': 'none', 'color': "gray", 'weight': 3}
                ).add_to(m)

                folium.GeoJson(
                    url_communes,
                    name="Communes membres",
                    style_function=lambda x: {'fillColor': 'none', 'color': 'gray', 'weight': 0.5, 'dashArray': '5, 5'}
                ).add_to(m)
        
        except Exception as e:
            st.error(f"Erreur technique de geo.api.gouv.fr : {e}")

        # Affichage dyamique selon le choix
        if choix == "Toute la Haute-Garonne":
            marker_cluster = MarkerCluster(name="Parc Social 31").add_to(m)
            for _, row in data_to_map.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=5, color='white', weight=0.5, fill=True,
                    fill_color=color_map.get(row['classe_ener_principale'], '#d3d3d3'),
                    fill_opacity=0.8,
                    popup=f"<b>{row['libelle_commune_insee']}</b><br>DPE: {row['classe_ener_principale']}<br>Logements: {row['nb_log']}"
                ).add_to(marker_cluster)

        else:
            for _, row in gdf_filtered.dropna(subset=['lat', 'lon']).iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=5,
                    color='white',
                    weight=0.5,
                    fill=True,
                    fill_color=color_map.get(row['classe_ener_principale'], '#d3d3d3'),
                    fill_opacity=0.9,
                    popup=f"Commune: {row['libelle_commune_insee']}<br>DPE: {row['classe_ener_principale']}<br>Logements: {row['nb_log']}"
                ).add_to(m)

        # 3. AJOUT DES BOUTONS DE CONTRÔLE
        # Contrôleur de couches
        folium.LayerControl(position='topright', collapsed=True).add_to(m)

        # 4. Affichage
        st_folium(m, width="100%", height=500, returned_objects=[])
    
    st.markdown("**Sources** : [Base de données nationale des bâtiments (RPLS & DPE)](https://hackathon.data.gouv.fr/datasets/61dc7157488f8cdb4283e3c3) | **Données géographiques** : [geo.api.gouv.fr](https://geo.api.gouv.fr/decoupage-administratif)")

with col_droite:
    
    with st.container(border=True):

        with st.spinner("Analyse statistique des données en cours..."):

            col_d1, col_d2 = st.columns(2)

            with col_d1:
                # === GRAPHIQUE 1 : QUANTITÉ VS QUALITÉ (EPCI OU COMMUNES) ===
                col_titre1, col_help1 = st.columns([0.9, 0.1])
                with col_titre1:
                    st.markdown(f"##### ➤ Volumétrie du parc et performance par :")
                with col_help1:
                    with st.popover("ℹ️", help="Clés de lecture"):
                        st.markdown(
                            """
                            Ce graphique juxtapose la volumétrie du parc (barres) et sa qualité énergétique moyenne (ligne). 
                            
                            - En vue EPCI, il met en lumière les territoires où se concentrent les enjeux de rénovation.
                            - En vue Communes, il permet d'identifier les communes au sein de l'EPCI qui contribuent le plus à ces enjeux.
                            
                            **Analyse :** Identifier les zones prioritaires pour les politiques de rénovation énergétique, en ciblant à la fois la masse critique et la performance.
                            """
                        )

                # --- SÉLECTEUR DE VUE ---
                vue_choisie = st.radio(
                    "",
                    ["EPCI", "Communes"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

                # --- LOGIQUE D'AFFICHAGE ---
                if vue_choisie == "EPCI":
                    # Préparation des données
                    df_plot = gdf.groupby('nom_epci').agg({
                        'nb_log': 'sum',
                        'dpe_score_num': 'mean'
                    }).reset_index().dropna()
                    df_plot = df_plot.sort_values('nb_log', ascending=False)
                    # Variables spécifiques
                    x_col = 'nom_epci'
                    colors = ['#EF553B' if x == choix else '#636EFA' for x in df_plot['nom_epci']]
                    hover_fmt = ""

                else:
                    # Préparation des données
                    df_plot = gdf_filtered.groupby('libelle_commune_insee').agg({
                        'nb_log': 'sum',
                        'dpe_score_num': 'mean'
                    }).reset_index().dropna()
                    df_plot = df_plot.sort_values('nb_log', ascending=False)
                    # Variables spécifiques
                    x_col = 'libelle_commune_insee'
                    colors = '#636EFA'
                    hover_fmt = "<b>%s</b>"

                # --- CRÉATION DU GRAPHIQUE COMMUN ---
                df_plot['dpe_label'] = df_plot['dpe_score_num'].apply(get_dpe_label)
                fig = make_subplots(specs=[[{"secondary_y": True}]])

                # BARRES : Nombre de logements
                fig.add_trace(
                    go.Bar(
                        x=df_plot[x_col],
                        y=df_plot['nb_log'],
                        name="Volumétrie",
                        marker_color=colors,
                        opacity=0.7,
                        hovertemplate="Logements : %{y}<extra></extra>"
                    ),
                    secondary_y=False,
                )

                # LIGNE : Score DPE moyen
                fig.add_trace(
                    go.Scatter(
                        x=df_plot[x_col],
                        y=df_plot['dpe_score_num'],
                        name="Qualité DPE",
                        customdata=df_plot['dpe_label'],
                        mode='lines+markers',
                        line=dict(color='#00CC96', width=3),
                        marker=dict(size=8 if vue_choisie == "EPCI" else 4),
                        hovertemplate="Score moyen : %{customdata}<extra></extra>"
                    ),
                    secondary_y=True,
                )

                # Design commun
                fig.update_layout(
                    height=350,
                    margin=dict(l=0, r=0, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode="x unified",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )

                fig.update_xaxes(
                    showticklabels=False, 
                    showgrid=False,
                    title_text="",
                    hoverformat=hover_fmt
                )

                fig.update_yaxes(secondary_y=False, showgrid=True, gridcolor='lightgrey')
                fig.update_yaxes(
                    secondary_y=True,
                    range=[1, 7],
                    tickvals=[1, 2, 3, 4, 5, 6, 7],
                    ticktext=['G', 'F', 'E', 'D', 'C', 'B', 'A'],
                    showgrid=False
                )

                st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

                # === GRAPHIQUE 2 : RÉPARTITION PAR CLASSE DPE (TREEMAP) ===

                col_titre2, col_help2 = st.columns([0.9, 0.1])
                with col_titre2:
                    st.markdown("##### ➤ Structure du parc || Poids relatif des étiquettes DPE")
                with col_help2:
                    with st.popover("ℹ️", help="Clés de lecture"):
                        st.markdown(
                            """
                            Ce graphique représente la décomposition du parc social par classe DPE.
        
                            * **Poids visuel :** La taille de chaque bloc est proportionnelle au nombre de bâtiments.
                            * **Performance globale :** 
                                * **A-B :** Haute performance (neuf/rénové).
                                * **C-D :** Performance moyenne.
                                * **E-F-G :** Passoires thermiques prioritaires.
                            
                            **Analyse :** Permet d'évaluer instantanément la maturité énergétique du patrimoine sélectionné.
                            """
                        )

                # 1. Préparation des données (Identique)
                ordre_dpe = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
                df_repart = gdf_filtered['classe_ener_principale'].value_counts().reindex(ordre_dpe, fill_value=0).reset_index()
                df_repart.columns = ['Classe', 'Nb_Batiments']

                # 2. Création de la Treemap
                fig_repart = px.treemap(
                    df_repart,
                    path=['Classe'], # Définit la hiérarchie (ici simple)
                    values='Nb_Batiments',
                    color='Classe',
                    color_discrete_map=color_map # Utilise ton dictionnaire de couleurs officiel
                )

                fig_repart.update_layout(
                    height=200, 
                    margin=dict(l=0, r=0, t=5, b=5),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )

                fig_repart.update_traces(
                    textinfo="label+value", # Affiche la lettre et le nombre
                    textfont=dict(size=16, color="white"),
                    hovertemplate="<b>Classe %{label}</b><br>%{value} bâtiments<extra></extra>",
                    marker_pad=dict(t=0, l=0, r=0, b=0) # Supprime les marges entre les blocs
                )

                st.plotly_chart(fig_repart, width='stretch', config={'displayModeBar': False})
            
            with col_d2:
                col_titre3, col_help3 = st.columns([0.9, 0.1])
                with col_titre3:
                    st.markdown("##### ➤ Dynamique de construction et performance thermique")
                with col_help3:
                    with st.popover("ℹ️", help="Clés de lecture"):
                        st.markdown("""
                        Ce graphique croise l'histoire du bâti, sa forme et sa performance actuelle.
                        
                        * **Volume (Haut) :** Nombre de logements construits. Identifie le poids historique de chaque période.
                        * **Morphologie (Milieu) :** Part de **Collectif** (bleu) vs **Individuel** (orange).
                        * **Performance (Bas) :** Évolution des étiquettes DPE. Le passage au "tout vert" (A-B) illustre l'efficacité des normes récentes.
                        
                        **Analyse :** La lecture verticale permet de lier les 3 métriques à la période de construction.
                        """)
                
                # 1. Préparation des données filtrées
                # Assurez-vous que 'type_batiment_dpe' est bien dans votre export GeoJSON
                df_hist = gdf_filtered.dropna(subset=['periode_construction_dpe', 'classe_ener_principale'])
                ordre_periodes = ["avant 1948", "1948-1974", "1975-1977", "1978-1982", 
                                "1983-1988", "1989-2000", "2001-2005", "2006-2012", "2013-2021"]
                df_hist['morpho'] = df_hist['type_batiment_dpe'].apply(get_morpho)

                # --- A. VOLUME (HAUT - Hauteur augmentée à 220px) ---
                df_vol = df_hist.groupby('periode_construction_dpe')['nb_log'].sum().reset_index()
                fig_v = px.bar(df_vol, x='periode_construction_dpe', y='nb_log', 
                            category_orders={'periode_construction_dpe': ordre_periodes}, height=200)
                fig_v.update_layout(margin=dict(l=60, r=10, t=10, b=0), showlegend=False,
                                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                    xaxis=dict(visible=False), yaxis=dict(title="Logements"))
                st.plotly_chart(fig_v, width="stretch", config={'displayModeBar': False})

                # --- B. MORPHOLOGIE (MILIEU - Hauteur augmentée à 120px) ---
                df_m = df_hist.groupby(['periode_construction_dpe', 'morpho'])['nb_log'].sum().reset_index()
                fig_m = px.bar(df_m, x='periode_construction_dpe', y='nb_log', color='morpho',
                            category_orders={'periode_construction_dpe': ordre_periodes}, height=150,
                            color_discrete_map={"Collectif": "#1f77b4", "Individuel": "#ff7f0e"})
                fig_m.update_layout(barmode='stack', barnorm='percent', showlegend=False,
                                    margin=dict(l=60, r=10, t=0, b=0),
                                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                    xaxis=dict(visible=False), 
                                    yaxis=dict(
                                        visible=True,
                                        tickmode='array',
                                        tickvals=[25, 50, 75, 100],
                                        title="Morphologie (%)",
                                        showgrid=True,
                                        gridcolor='rgba(200,200,200,0.1)'
                                    ))
                st.plotly_chart(fig_m, width="stretch", config={'displayModeBar': False})

                # --- C. PERFORMANCE (BAS - Hauteur augmentée à 450px pour remplir le vide) ---
                df_p = df_hist.groupby(['periode_construction_dpe', 'classe_ener_principale'])['nb_log'].sum().reset_index()
                fig_p = px.bar(df_p, x='periode_construction_dpe', y='nb_log', color='classe_ener_principale',
                            color_discrete_map=color_map, category_orders={'periode_construction_dpe': ordre_periodes}, height=300)
                fig_p.update_layout(barmode='stack', barnorm='percent', showlegend=False,
                                    margin=dict(l=60, r=10, t=0, b=80),
                                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                    xaxis=dict(visible=True, title=None, tickangle=-45),
                                    yaxis=dict(
                                        visible=True,
                                        tickmode='array',
                                        tickvals=[25, 50, 75, 100],
                                        title="DPE (%)",
                                        showgrid=True,
                                        gridcolor='rgba(200,200,200,0.1)'
                                    ))
                st.plotly_chart(fig_p, width="stretch", config={'displayModeBar': False})