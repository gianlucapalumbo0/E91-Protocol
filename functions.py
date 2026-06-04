
from dotenv import load_dotenv
import os
import random
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.fake_provider import FakeFez

# Carica le variabili d'ambiente dal file .env
load_dotenv()




def quantum_random_basis_gen(n: int) -> list[int]:
    """
    Genera una sequenza di n interi casuali in {0, 1, 2} tramite simulazione locale rumorosa.

    Il metodo implementa un approccio QRNG (Quantum Random Number Generator) ibrido:
    recupera il modello di rumore calibrato e aggiornato (vulnerabilità termiche, stocastiche 
    e di sfasamento) da una QPU IBM reale via cloud, ma esegue il circuito istantaneamente 
    sul backend di simulazione locale (AerSimulator), bypassando le code remote.

    Tutte le configurazioni di autenticazione e di puntamento all'hardware sono delegate
    alle variabili d'ambiente caricate a runtime.
    """

    
    # Caricamento delle variabili d'ambiente
    backend_name = os.environ["IBMQ_BACKEND"]
    token = os.getenv("IBMQ_TOKEN")

    # Controllo del token. Questo evita tentativi di connessione inutili
    if not token:
        raise ValueError("IBMQ_TOKEN non trovato nel file .env.")
            
    print(f"[QRNG] Download del modello di rumore live per '{backend_name}' da IBM Quantum...")

    try:    
        # Connessione al cloud IBM e recupero del backend reale
        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=token
        )
        real_backend = service.backend(backend_name)
        
        # Creazione del simulatore locale con rumore reale
        backend = AerSimulator.from_backend(real_backend)
        print(f"[QRNG] Simulatore locale pronto con il rumore REALE di {backend_name}. (Nessuna coda cloud!)")
    
    # Caso in cui qualcosa va storto
    except Exception as e:
        print(f"[CRITICAL] Errore irreversibile di connessione o autenticazione con IBM Quantum.")
        raise ConnectionError(f"Impossibile scaricare il rumore live di {backend_name} dovuto a: {e}") from e

  
    # Costruzione del circuito quantistico
    # il circuito prende in input 2 qubit, li mette in sovrapposizione e li misura, generando 
    # 4 possibili esiti (00, 01, 10, 11)
    qc = QuantumCircuit(2, 2)
    qc.h([0, 1])
    qc.measure([0, 1], [0, 1])

    # Calcolo del numero di shots
    shots = int(n * (4 / 3) * 1.5)
    
    # Esecuzione del circuito
    print(f"[QRNG] Esecuzione simulazione rumorosa in locale ({shots} shots)...")
    transpiled = transpile(qc, backend)
    job = backend.run(transpiled, shots=shots)
    result = job.result()
    counts = result.get_counts()

    
    # Post-Processing: mappatura binaria a ternaria
    # mappiamo 00 in 0, 01 in 1, 10 in 2 e scartiamo 11
    valid_outcomes = []
    for outcome, count in counts.items():
        if outcome == "00":
            valid_outcomes.extend([0] * count)
        elif outcome == "01":
            valid_outcomes.extend([1] * count)
        elif outcome == "10":
            valid_outcomes.extend([2] * count)
    

    # Rimozione dei bias sequenziali tramite permutazione casuale degli elementi estratti
    random.shuffle(valid_outcomes)

    # Mitigazione del rumore estremo: previene il sotto-campionamento (Underflow)
    if len(valid_outcomes) < n:
        print(f"[QRNG] Avviso: Campioni quantistici insufficienti ({len(valid_outcomes)}/{n}) a causa del rumore. Integro i rimanenti.")
        # Padding deterministico per mantenere l'integrità strutturale richiesta dai simulatori di rete
        while len(valid_outcomes) < n:
            valid_outcomes.append(random.choice([0, 1, 2]))

    return valid_outcomes[:n]





def Process_E91_Bases(alice_ids, bob_ids, basisA, basisB, measA, measB):
    """
    Questa funzione esegue il post-processing del protocollo E91. Serve a ricostruire
    quali round appartengono alla chiave e quali round appartengono al test CHSH
    """
    
    # Inizializzazione delle strutture dati per chiave e test CHSH
    keyA = [] 
    keyB = [] 
    chsh_pairs = {(0,0): [], (0,1): [], (2,0): [], (2,1): []} 

    # Mappa i dati ricevuti usando l'ID come chiave. id -> (base, misura)
    # questo serve a ricostriire l'ordine corretto dei quib ricevuti e 
    # dunque quali qubit appartengono alla stessa coppia EPR
    alice_data = {alice_ids[i]: (basisA[i], measA[i]) for i in range(len(alice_ids))}
    bob_data = {bob_ids[i]: (basisB[i], measB[i]) for i in range(len(bob_ids))}

    # Trova gli ID comuni (qubit ricevuti sia da Alice che da Bob)
    common_ids = sorted(list(set(alice_ids) & set(bob_ids)))

    for pid in common_ids:
        bA, mA = alice_data[pid]
        bB, mB = bob_data[pid]

        # Test CHSH
        if bA in (0,2) and bB in (0,1): 
            chsh_pairs[(bA, bB)].append((mA, mB))

        # Generazione della Chiave
        if bA == 1 and bB == 0: 
            keyA.append(mA)
            keyB.append(mB)

    return keyA, keyB, chsh_pairs



def Calculate_CHSH(chsh_pairs):
    """
    Questa funzione calcola il valore D della disuguaglianza CHSH, che serve a verificare
    se il sistema si comporta in modo quantistico (violazione) o classico
    """

    # Dizionario che conterrà le correlazioni E(a,b) per ciascuna combinazione di basi
    E = {}

    # Itera su tutte le combinazioni di basi e sui risultati associati
    for (a_basis, b_basis), results in chsh_pairs.items():  

        # Se non ci sono risultati per questa combinazione di basi, 
        # assegniamo correlazione zero per evitare divisioni per zero
        if len(results) == 0: 
            E[(a_basis, b_basis)] = 0
            continue

        # Conta quante volte Alice e Bob hanno ottenuto lo stesso risultato (00 o 11)
        same = sum(1 for m in results if m[0] == m[1]) 

        # Conta quante volte i risultati sono diversi (01 o 10)
        diff = len(results) - same 

        # Calcola la correlazione E(a,b) = (same - diff) / totale
        # Valore compreso tra -1 e +1
        E[(a_basis, b_basis)] = (same - diff) / len(results)
        

    # Calcolo del valore S della disuguaglianza CHSH:
    # S = E(0,0) - E(0,1) + E(2,0) + E(2,1)
    # Questa è la forma standard della CHSH per le basi usate in E91
    S = E[(0,0)] - E[(0,1)] + E[(2,0)] + E[(2,1)] 

    # Stampa di debug: mostra le correlazioni calcolate per ciascuna combinazione
    print(f"E00={E[(0,0)]:.4f}, E01={E[(0,1)]:.4f}, E20={E[(2,0)]:.4f}, E21={E[(2,1)]:.4f}") 

    # Restituiamo il valore assoluto di S
    return abs(S)