import streamlit as st
import pandas as pd
import numpy as np
from rapidfuzz import fuzz

st.title('Argos - Open Source')

st.header('Disclaimer')
st.write('Argos permet de vérifier si un de vos assurés est dans la liste du Trésor des gels des avoirs. Cette vérification fait parti du dispositf réglementaire de la LCB-FT.')
st.write('Argos est développé par Hestialytics et est mise en open-source. Des bugs peuvent subsister.')
st.write('Si vous souhaitez avoir une version plus adaptez à vous besoins, contactez nous à contact@hestialytics.com')
st.divider()

st.header('Format des données')
st.write('Le fichier à uploader doit comporter au moins trois colonnes : *contractId*, *nom*, *prenom*')

## Loading data
@st.cache_data(ttl=24*60*60)
def telechargement(url):
    res = pd.read_json(url)
    return res

data_load_state = st.text('Téléchargement de la base des gels des avoirs ...')
fileAPI = 'https://gels-avoirs.dgtresor.gouv.fr/ApiPublic/api/v1/publication/derniere-publication-fichier-json'
data = telechargement(fileAPI)
lastDateData = data['Publications']['DatePublication'][0:10]
data = data['Publications']['PublicationDetail']
idsGel = []
for ii in data:
    idsGel.append(ii['IdRegistre'])
data_load_state.text('La dernière date de mise à jour de la base des gels des avoirs est le '+lastDateData)

## Importing
uploaded_file = st.file_uploader("Uploader le fichier des assurés à vérifier",type={"csv"})

## Analyse
if uploaded_file is not None:
    
    portfolio = pd.read_csv(uploaded_file,sep=';')
    st.info('La base contient '+ str(len(portfolio))+ ' assurés à vérifier')
    st.divider()

    data_process_state = st.text('Préparation des données...')
    
    ## Data Management for name in gel
    gels =pd.DataFrame(columns = ['idRegistre', 'nom'])
    for ii in data:
        if ii['Nature'] == 'Personne physique':
            idRegistre = ii['IdRegistre']
            nom = ii['Nom']
            detail = ii['RegistreDetail']
            # Checking attributs
            attributs =[]
            for nn in detail:
                attributs.append(nn['TypeChamp'])
            # Prenom
            if 'PRENOM' in attributs:
                prenom = detail[attributs.index('PRENOM')]['Valeur'][0]['Prenom']
                prenom = prenom.strip()
                prenomNom = prenom.lower() + ' ' + nom.lower()
                prenomNom = prenomNom.strip()
                new = pd.DataFrame({'idRegistre':[idRegistre], 'nom':[prenomNom]})
                gels = pd.concat([gels, new], ignore_index=True)
            # Alias
            if 'ALIAS' in attributs:
                alias = detail[attributs.index('ALIAS')]
                for aa in alias['Valeur']:
                    if len(aa['Alias'].split()) > 1:
                        new = pd.DataFrame({'idRegistre':[idRegistre], 'nom':[aa['Alias'].lower().strip()]})
                        gels = pd.concat([gels, new], ignore_index=True)

    data_process_state.text('Calcul des similarités ...')
    computing = st.progress(0)
    ## Similarities
    for aa in range(len(portfolio)):
        computing.progress(aa/len(portfolio))
        prenomAssure = portfolio['prenom'][aa]
        prenomAssure = prenomAssure.strip()
        assure = prenomAssure.lower() + ' ' + portfolio['nom'][aa].lower()
        assure= assure.strip()
        sims=[]
        for gg in range(len(gels)):
            gelName = gels['nom'][gg]
            ratio1 = (fuzz.ratio(assure,gelName)+fuzz.token_ratio(assure,gelName))/2
            extremString = gelName.split()
            newGelName = extremString[0]+' '+extremString[-1]
            ratio2 = (fuzz.ratio(assure,newGelName)+fuzz.token_ratio(assure,newGelName))/2
            sims.append(max(ratio1,ratio2))
        kept = np.argmax(sims)
        new = pd.DataFrame({'assure':[prenomAssure + ' ' +portfolio['nom'][aa]],
                            'contractId':[portfolio['contractId'][aa]],
                            'idRegistre':[gels['idRegistre'][kept]],
                            'nomGel':[gels['nom'][kept]],
                            'score':[sims[kept]]})
        if aa == 0:
            similarities = new
        else:
            similarities = pd.concat([similarities, new], ignore_index=True)
    similarities=similarities.sort_values('score',ascending=False)
    computing.empty()
    data_process_state.empty()

    ## Threshold
    thre = 91
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False,sep=';').encode('utf-8')
    
    concern = similarities[similarities.score > thre].reset_index()
    similaritiesCSV = convert_df(similarities)
    if len(concern)==0:
        st.success('Aucun assuré ne semble être dans la liste des avoirs gelés')
        st.balloons()
        st.download_button("Télécharger le fichier des meilleurs concordances",
                           similaritiesCSV,"concordanceScore.csv")
    else:
        st.error('Il y a ' + str(len(concern)) + ' assurés avec une potentielle concordance')
        st.download_button("Télécharger le fichier des meilleurs concordances",
                           similaritiesCSV,"concordanceScore.csv")
        st.dataframe(concern)
        st.write('Liens vers les fiches détaillés du Registre des gels des avoirs')
        urlRegistre='https://gels-avoirs.dgtresor.gouv.fr/Gels/RegistreDetail?idRegistre='
        for cc in range(len(concern)):
            st.link_button(concern['assure'][cc]+' - Contrat '+ str(concern['contractId'][cc]),
                            urlRegistre+str(concern['idRegistre'][cc]))
