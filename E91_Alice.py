import numpy as np
import time
from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumProgram
from netsquid.components.instructions import INSTR_MEASURE, INSTR_ROT_Y
from functions import quantum_random_basis_gen

class QG_A_measure(QuantumProgram):
    """
    Questa classe rappresenta il programma di misura di Alice nel protocollo E91
    """
    def __init__(self, basisList):
        # Salva la lista delle basi che Alice deve usare per ogni qubit
        self.basisList = basisList

        # Inizializza correttamente la classe base QuantumProgram
        super().__init__()

    def program(self):
        # Itera su tutti i qubit e sulle basi corrispondenti
        for i, basis in enumerate(self.basisList):
            # base 0 -> 0°
            if basis == 0:
                pass
            # base 1 -> 45°
            elif basis == 1:
                self.apply(INSTR_ROT_Y, [i], angle=-np.pi/4)
                # base 2 -> 90°
            elif basis == 2:
                self.apply(INSTR_ROT_Y, [i], angle=-np.pi/2)

            # Dopo la rotazione, Alice misura nella base Z (computazionale) e salva il risultato in output_key
            self.apply(INSTR_MEASURE, [i], output_key=str(i), physical=True)

        # Esegue tutte le misure in parallelo
        yield self.run(parallel=True)



class AliceProtocol(NodeProtocol):
    """
    Questa classe implementa tutto il comportamento di Alice nel protocollo E91
    """
    def __init__(self, node, processor, num_bits, perf, port_names=None):
        # Inizializza la classe base con il nodo di Alice
        super().__init__(node)

        # Riferimenti al nodo, processore quantistico e parametri del protocollo
        self.node = node
        self.processor = processor
        self.num_bits = num_bits
        self.perf = perf

        # Se non vengono specificati nomi delle porte, usa quelli di default
        if port_names is None:
            port_names = ["qubit_in", "classical_in", "classical_out"]
        self.portQ, self.portC1, self.portC2 = port_names
        
        # Genera le basi computazionali per tutti i qubit che Alice dovrebbe ricevere (serve per il post-processing)
        self.full_basisList = quantum_random_basis_gen(num_bits)

        # Lista delle basi effettivamente usate (solo per i qubit ricevuti)
        self.basisList = []     

        # Risultati locali delle misure di Alice
        self.loc_measRes = []

    def run(self):
        print(f"[Alice] Waiting for {self.num_bits} qubits...")

        # Attende l'arrivo dei qubit sulla porta quantistica
        yield self.await_port_input(self.node.ports[self.portQ])
        qubits = self.node.ports[self.portQ].rx_input().items

        # Se non arriva nulla, termina il protocollo
        if not qubits:
            print(f"[Alice] No qubits received, aborting.")
            return

        # Estrae gli ID delle coppie EPR e associa ogni qubit al suo ID
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

        print(f"[Alice] Received {actual_num} qubits (expected {self.num_bits})")

        # Registra statistiche dei qubit ricevuti
        for _ in sorted_qubits:
            self.perf.record_qubit_received("alice")

        # Inserisce i qubit nel processore quantistico
        self.processor.put(sorted_qubits)

        # Esegue il programma di misura di Alice
        t_start = time.time()
        measure_program = QG_A_measure(self.basisList)
        positions = list(range(actual_num))

        self.processor.execute_program(measure_program, qubit_mapping=positions)
        yield self.await_program(self.processor)
        t_end = time.time()

        # Registra il tempo di computazione
        self.perf.record_computation_time("alice", t_end - t_start)

        for i in range(actual_num):
            self.loc_measRes.append(measure_program.output[str(i)][0])

        print(f"[Alice] Measurements complete")

        # Attende le basi di Bob
        print(f"[Alice] Waiting for Bob's bases...")
        yield self.await_port_input(self.node.ports[self.portC1])
        bob_bases = self.node.ports[self.portC1].rx_input().items
        self.perf.record_classical_message()

        # Invia le basi usate da Alice
        print(f"[Alice] Sending bases to Bob...")
        self.node.ports[self.portC2].tx_output(self.basisList)
        self.perf.record_classical_message()

        print(f"[Alice] Protocol complete")
        self.perf.alice_done = True