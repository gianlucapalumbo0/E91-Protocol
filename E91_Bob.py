import numpy as np
import time
from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumProgram
from netsquid.components.instructions import INSTR_MEASURE, INSTR_ROT_Y
from functions import quantum_random_basis_gen

class QG_B_measure(QuantumProgram):
    """
    Questa classe rappresenta il programma di misura di Bob nel protocollo E91. 
    Per ogni qubit che riceve Bob lo misura in una delle tre basi possibili (0, 1, 2) che 
    corrispondono a rotazioni di -pi/4, -pi/2 e -3pi/4 rispettivamente.
    """
    def __init__(self, basisList):
        # Salviamo una lista delle basi che Bob deve usare per ogni qubit
        self.basisList = basisList

        # Inizializziamo la classe madre QuantumProgram
        super().__init__()

    def program(self):
        # Iteriamo su tutti i qubit che Bob deve misurare, dove i è l'indice del qubit
        # e basis è la base scelta da Bob per quel qubit
        for i, basis in enumerate(self.basisList):
            if basis == 0:
                # base 0 -> angolo -45°
                self.apply(INSTR_ROT_Y, [i], angle=-np.pi/4)
            elif basis == 1:
                # base 1 -> angolo -90°
                self.apply(INSTR_ROT_Y, [i], angle=-np.pi/2)
            elif basis == 2:
                # base 2 -> angolo -135°
                self.apply(INSTR_ROT_Y, [i], angle=-3*np.pi/4)

            # Dopo la rotazione, Bob misura nella base Z (computazionale) e salva il risultato in output_key
            self.apply(INSTR_MEASURE, [i], output_key=str(i), physical=True)

        # Esegue il programma in parallelo, misurando tutti i qubit contemporaneamente
        yield self.run(parallel=True)



class BobProtocol(NodeProtocol):
    """
    Questa class implementa il comportament completo di Bob nel protocollo E91
    """
    def __init__(self, node, processor, num_bits, perf, port_names=None):
        # Inizializza la classe base NodeProtocol con il nodo di Bob
        super().__init__(node)

        # Riferimenti al nodo, al processore quantistico e ai parametri del protocollo
        self.node = node
        self.processor = processor
        self.num_bits = num_bits
        self.perf = perf

        # Se non vengono specificati i nomi delle porte, usa quelli di default
        if port_names is None:
            port_names = ["qubit_in", "classical_out", "classical_in"]
        self.portQ, self.portC1, self.portC2 = port_names

        # Genera tutte le basi quantistiche (una per ogni possibile qubit)
        self.full_basisList = quantum_random_basis_gen(num_bits)

        # Lista delle basi effettivamente usate
        self.basisList = []

        # Risultati locali delle misure di Bob
        self.loc_measRes = []

    def run(self):
        print(f"[Bob] Waiting for {self.num_bits} qubits...")

        # Bob attende l'arrivo dei qubit sulla porta quantistica
        yield self.await_port_input(self.node.ports[self.portQ])
        qubits = self.node.ports[self.portQ].rx_input().items

        # Se non arriva nulla, termina il protocollo
        if not qubits:
            print(f"[Bob] No qubits received, aborting.")
            return

        # Estrae l'ID di ogni qubit per riallineare i round
        qubits_with_ids = [(getattr(q, '_meta', {}).get('pair_id', 0), q) for q in qubits]

        # Ordina i qubit in base al loro ID
        qubits_with_ids.sort(key=lambda x: x[0])

        # Estrae i qubit ordinati e gli ID ordinati
        sorted_qubits = [q for _, q in qubits_with_ids]
        received_ids = [i for i, _ in qubits_with_ids]

        # Salva gli ID ricevuti (serve per il post-processing)
        self.received_ids = received_ids  

        # Seleziona le basi corrispondenti agli ID effettivamente ricevuti
        self.basisList = [self.full_basisList[idx] for idx in received_ids]
        actual_num = len(sorted_qubits)

        print(f"[Bob] Received {actual_num} qubits (expected {self.num_bits})")

        # Registra le statistiche dei qubit ricevuti
        for _ in sorted_qubits:
            self.perf.record_qubit_received("bob")

        # Inserisce i qubit nel processore quantistico
        self.processor.put(sorted_qubits)

        # Esegue il programma di misura di Bob
        t_start = time.time()
        measure_program = QG_B_measure(self.basisList)
        positions = list(range(actual_num))

        self.processor.execute_program(measure_program, qubit_mapping=positions)
        yield self.await_program(self.processor)
        t_end = time.time()

        # Registra il tempo di computazione
        self.perf.record_computation_time("bob", t_end - t_start)

        # Estrae i risultati delle misure
        for i in range(actual_num):
            self.loc_measRes.append(measure_program.output[str(i)][0])

        print(f"[Bob] Measurements complete")

        # Invia le basi usate a Alice
        print(f"[Bob] Sending bases to Alice...")
        self.node.ports[self.portC1].tx_output(self.basisList)
        self.perf.record_classical_message()

        # Attende le basi di Alice
        print(f"[Bob] Waiting for Alice's bases...")
        yield self.await_port_input(self.node.ports[self.portC2])
        self.basis_A = self.node.ports[self.portC2].rx_input().items
        self.perf.record_classical_message()

        print(f"[Bob] Protocol complete")
        self.perf.bob_done = True