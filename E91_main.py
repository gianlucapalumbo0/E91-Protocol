import netsquid as ns
import netsquid.qubits.operators as ops  

from netsquid.nodes import Node
from netsquid.components import QuantumProcessor, PhysicalInstruction
from netsquid.components.instructions import INSTR_MEASURE, INSTR_ROT_Y
from netsquid.components.qchannel import QuantumChannel
from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.models import FibreDelayModel, FibreLossModel
from netsquid.components.models.qerrormodels import DepolarNoiseModel
from netsquid.qubits import create_qubits

from E91_Alice import AliceProtocol
from E91_Bob import BobProtocol
from functions import Process_E91_Bases, Calculate_CHSH
from performance import PerformanceTracker
from E91_Eve import EveProtocol


def generate_bell_pairs(num_pairs, perf_tracker):
    """
    Questa funzione genera coppie Bell
    """

    # Liste che conterranno i qubit destinati ad Alice e Bob
    qubits_alice = []
    qubits_bob = []
    print(f"\n[Source] Generating {num_pairs} Bell pairs...")

    # Ciclo per generare num_pairs coppie EPR
    for i in range(num_pairs):

        # Crea due qubit inizializzati nello stato |0⟩|0⟩
        q1, q2 = create_qubits(2)

        # Applica Hadamard al primo qubit: |0⟩ → (|0⟩ + |1⟩)/√2
        ns.qubits.operate(q1, ops.H)

        # Applica CNOT con q1 come controllo e q2 come target
        # Questo crea lo stato di Bell |Φ+⟩ = (|00⟩ + |11⟩)/√2
        ns.qubits.operate([q1, q2], ops.CNOT)

        # Assegna un ID univoco alla coppia (serve per riallineare i round)
        q1._meta = {'pair_id': i}
        q2._meta = {'pair_id': i}

        # Inserisce i qubit nelle rispettive liste
        qubits_alice.append(q1)
        qubits_bob.append(q2)

        # Registra che una coppia EPR è stata generata
        perf_tracker.record_epr_sent()

        # Stampa di progresso ogni 100 coppie
        if (i + 1) % 100 == 0:
            print(f"[Source] Generated {i + 1}/{num_pairs} pairs")
    
    # Restituisce le due liste di qubit entangled
    return qubits_alice, qubits_bob


def run_e91(num_pairs=5000, eve_active=False):
    """
    Questa funzione esegue il protocollo E91
    """
    # Header di avvio
    print("\n" + "="*70)
    print("STARTING E91 PROTOCOL WITH DEPOLARIZING NOISE")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Number of EPR pairs: {num_pairs}")
    print(f"  Noise: Enabled (depolarizing rate = 0.02)")
    
    # Reset della simulazione NetSquid
    ns.sim_reset()

    # Performance tracker per statistiche e misure
    perf = PerformanceTracker(num_pairs)
    perf.start_simulation()
    
    # Creazione dei nodi
    alice_node = Node("Alice", port_names=["qubit_in", "classical_in", "classical_out"])
    bob_node = Node("Bob", port_names=["qubit_in", "classical_in", "classical_out"])
    source_node = Node("EPR_Source", port_names=["out_alice", "out_bob"])
    
    # Nodo intermedio per Eve (attacco Intercept-Resend)
    eve_node = Node("Eve", port_names=["qubit_in", "qubit_out"])
    
    # Processori quantistici
    alice_processor = QuantumProcessor("AliceProc", num_positions=num_pairs,
        phys_instructions=[
            PhysicalInstruction(INSTR_MEASURE, duration=100),
            PhysicalInstruction(INSTR_ROT_Y, duration=10)
        ])
    
    bob_processor = QuantumProcessor("BobProc", num_positions=num_pairs,
        phys_instructions=[
            PhysicalInstruction(INSTR_MEASURE, duration=100),
            PhysicalInstruction(INSTR_ROT_Y, duration=10)
        ])
    
    # Modello di rumore depolarizzante
    noise_model = DepolarNoiseModel(depolar_rate=0.02, time_independent=True)

    # Canale quantistico verso Alice
    qchannel_alice = QuantumChannel("Q_Alice", length=10,
    models={
        "delay_model": FibreDelayModel(c=2e5),
        "quantum_noise_model": noise_model,
        "quantum_loss_model": FibreLossModel(p_loss_length=0.045)
    })

    # Canale quantistico verso Bob (diviso in due parti per inserire Eve)
    qchannel_bob_part1 = QuantumChannel("Q_Bob_Sorgente_A_Eve", length=5,
    models={
        "delay_model": FibreDelayModel(c=2e5),
        "quantum_noise_model": noise_model,
        "quantum_loss_model": FibreLossModel(p_loss_length=0.045)
    })

    qchannel_bob_part2 = QuantumChannel("Q_Bob_Eve_A_Bob", length=5,
    models={
        "delay_model": FibreDelayModel(c=2e5),
        "quantum_noise_model": noise_model,
        "quantum_loss_model": FibreLossModel(p_loss_length=0.045)
    })
    
    # Connessione dei canali quantistici
    source_node.ports["out_alice"].connect(qchannel_alice.ports["send"])
    qchannel_alice.ports["recv"].connect(alice_node.ports["qubit_in"])
    
    
    source_node.ports["out_bob"].connect(qchannel_bob_part1.ports["send"])
    qchannel_bob_part1.ports["recv"].connect(eve_node.ports["qubit_in"])
    
    eve_node.ports["qubit_out"].connect(qchannel_bob_part2.ports["send"])
    qchannel_bob_part2.ports["recv"].connect(bob_node.ports["qubit_in"])

    # Canali classici
    classical_ab = ClassicalChannel("C_A2B", length=10, models={"delay_model": FibreDelayModel(c=2e5)})
    classical_ba = ClassicalChannel("C_B2A", length=10, models={"delay_model": FibreDelayModel(c=2e5)})
    
    # Collegamento dei canali classici
    alice_node.ports["classical_out"].connect(classical_ab.ports["send"])
    bob_node.ports["classical_in"].connect(classical_ab.ports["recv"])
    bob_node.ports["classical_out"].connect(classical_ba.ports["send"])
    alice_node.ports["classical_in"].connect(classical_ba.ports["recv"])
    
    # Protocolli di Alice, Bob ed Eve
    alice_proto = AliceProtocol(alice_node, alice_processor, num_pairs, perf)
    bob_proto = BobProtocol(bob_node, bob_processor, num_pairs, perf)
    eve_proto = EveProtocol(eve_node, active=eve_active)
    
    # Avvio dei protocolli
    alice_proto.start()
    bob_proto.start()
    eve_proto.start() 
    
    # Generazione delle coppie EPR
    alice_qubits, bob_qubits = generate_bell_pairs(num_pairs, perf)
    
    print(f"\n[Source] Sending qubits to Alice and Bob...")
    source_node.ports["out_alice"].tx_output(alice_qubits)
    source_node.ports["out_bob"].tx_output(bob_qubits)
    
    # Avvio della simulazione
    print(f"\n[Main] Running simulation...")
    ns.sim_run()
    
    # Post-Processing
    print(f"\n[Main] Post-processing...")
    alice_key, bob_key, chsh_pairs = Process_E91_Bases(
        alice_proto.received_ids, bob_proto.received_ids,
        alice_proto.basisList, bob_proto.basisList,
        alice_proto.loc_measRes, bob_proto.loc_measRes
    )
    
    # Calcolo QBER
    min_len = min(len(alice_key), len(bob_key))
    mismatches = sum(1 for i in range(min_len) if alice_key[i] != bob_key[i])
    perf.record_basis_match(len(alice_key))
    perf.record_mismatches(mismatches)
    
    # Calcolo CHSH
    chsh_value = Calculate_CHSH(chsh_pairs)
    
    # Fine simulazione e report
    perf.end_simulation()
    perf.report()
    
    # Risultati CHSH
    print(f"\n[CHSH RESULT]")
    print(f"  S value:           {chsh_value:.4f}")
    print(f"  Quantum limit:     2.8284")
    print(f"  Classical limit:   2.0000")
    
    if abs(chsh_value) > 2:
        print(f"  Result:            V QUANTUM VIOLATION")
    else:
        print(f"  Result:            X No violation (classical)")
    
    return alice_key, bob_key, chsh_value


if __name__ == "__main__":
    print("\n" + "█"*70)
    print("█" + " " * 68 + "█")
    print("█" + " " * 20 + "E91 QUANTUM KEY DISTRIBUTION" + " " * 20 + "█")
    print("█" + " " * 68 + "█")
    print("█"*70)
    
    print("\n" + "─"*70)
    print("STARTING SIMULATION IN SAFE MODE (WITHOUT ATTACK)")
    print("─"*70)
    keyA, keyB, S = run_e91(num_pairs=5000, eve_active=False)
    
    print(f"\n[FINAL KEYS SAFE MODE - First 50 bits]")
    print(f"  Alice: {''.join(map(str, keyA[:50]))}...")
    print(f"  Bob:   {''.join(map(str, keyB[:50]))}...")
    
    user_response = input("\nDo you want to run a second simulation ACTIVATING Eve's attack? (yes/no): ").strip().lower()
    attack = (user_response == "yes" or user_response == "y")
    
    if attack:
        print("\n" + "─"*70)
        print("STARTING SECOND SIMULATION IN UNDER-ATTACK MODE")
        print("─"*70)
        
        keyA_attack, keyB_attack, S_attack = run_e91(num_pairs=5000, eve_active=True)
        
        print(f"\n[FINAL KEYS UNDER ATTACK - First 50 bits]")
        print(f"  Alice: {''.join(map(str, keyA_attack[:50]))}...")
        print(f"  Bob:   {''.join(map(str, keyB_attack[:50]))}...")
    else:
        print("\nSimulation finished. No attack executed.")