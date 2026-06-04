import time


class PerformanceTracker:
    """
    Raccoglie e gestisce le metriche di performance durante la simulazione
    del protocollo quantistico E91.

    Ogni attributo tiene traccia di una specifica qualità fisica o computazionale
    utile a valutare l'efficienza del protocollo.
    """

    def __init__(self, num_pairs):
        """Inizializza i contatori e i timestamp della simulazione."""

        # Numero totale di coppie EPR che la simulazione dovrebbe generare
        self.num_pairs = num_pairs 

        # Contatore delle coppie EPR effettivamente inviate dalla sorgente
        self.sent_epr_pairs = 0 

        # Qubit ricevuti da Alice e Bob (servono per stimare la perdita del canale)
        self.received_qubits_alice = 0
        self.received_qubits_bob = 0 

        # Numero di round in cui le basi di Alice e Bob coicidono (raw key)
        self.matched_bases = 0 

        # Numero di bit discordanti dopo lo sifting (serve per il QBER)
        self.mismatched_bits = 0 

        # Numero totale di messaggi scambiati sul canale classico
        self.classical_messages = 0 

        # Tempo totale di calcolo eseguito da Alice e Bob
        self.computation_time_alice = 0.0 
        self.computation_time_bob = 0.0 

        # Timestamp di inizio e fine simulazione
        self.sim_start = None 
        self.sim_end = None 

        # Flag per sapere se Alice e Bob hanno terminato
        self.alice_done = False 
        self.bob_done = False 

    
    def start_simulation(self):
        """Registra l'istante di inizio della simulazione."""
        self.sim_start = time.time()

    
    def end_simulation(self):
        """Registra l'istante di fine della simulazione."""
        self.sim_end = time.time()


    def record_epr_sent(self):
        """Incrementa il contatore delle coppie EPR generate dalla sorgente."""
        self.sent_epr_pairs += 1


    def record_qubit_received(self, party):
        """
        Registra che un qubit è stato ricevuto da Alice o Bob.
        Questo serve per calcolare la perdita del canale quantistico.

        Args:
            party (str): 'alice' o 'bob'.
        """
        if party == "alice":
            self.received_qubits_alice += 1
        elif party == "bob":
            self.received_qubits_bob += 1


    
    def record_basis_match(self, matched):
        """
        Registra il numero di round in cui le basi coincidono.
        Questo valore rappresenta la lunghezza della raw key.
        """
        self.matched_bases = matched

    
    def record_mismatches(self, mismatches):
        """
        Registra quanti bit risultano discordanti dopo lo sifting.
        Serve per calcolare il QBER.
        """
        self.mismatched_bits = mismatches

    
    def record_classical_message(self):
        """Incrementa il numero di messaggi scambiati sul canale classico."""
        self.classical_messages += 1

  
    def record_computation_time(self, party, duration):
        """
        Registra il tempo di calcolo impiegato da Alice o Bob.

        Args:
            party (str): 'alice' o 'bob'.
            duration (float): Tempo in secondi.
        """
        if party == "alice":
            self.computation_time_alice = duration
        elif party == "bob":
            self.computation_time_bob = duration


    1
    def report(self):
        """
        Calcola tutte le metriche derivate della simulazione:
        - QBER
        - Loss Rate del canale quantistico
        - Throughput (bit utili al secondo)
        - Tempi di calcolo
        - Overhead classico

        e stampa un report leggibile.
        """

        # Durata totale della simulazione
        duration = self.sim_end - self.sim_start if self.sim_end else 0 

        # Numero di bit della raw key
        raw_key_bits = self.matched_bases 

        # Quantum Bit Error Rate (percentuale di bit discordanti)
        qber = (self.mismatched_bits / raw_key_bits * 100) if raw_key_bits > 0 else 0 

        # Calcolo del tasso di perdita per Alice e Bob
        # Protezione contro divisione per zero
        loss_rate_alice = max(0.0, 1 - (self.received_qubits_alice / self.sent_epr_pairs)) if self.sent_epr_pairs > 0 else 0 
        loss_rate_bob = max(0.0, 1 - (self.received_qubits_bob / self.sent_epr_pairs)) if self.sent_epr_pairs > 0 else 0 

        # Perdita media del canale
        avg_loss = (loss_rate_alice + loss_rate_bob) / 2 

        # Throughput: bit utili generati al secondo
        throughput = raw_key_bits / duration if duration > 0 else 0 

        # Tempo di calcolo totale e medio per round.
        total_comp = self.computation_time_alice + self.computation_time_bob 
        avg_computation = total_comp / (2 * self.num_pairs) if self.num_pairs > 0 else 0 

        # Stampa del report finale
        print("\n" + "="*60)
        print("E91 PROTOCOL PERFORMANCE REPORT")
        print("="*60)
        print(f"  EPR Pairs Sent:         {self.sent_epr_pairs}")
        print(f"  Raw Key Bits:           {raw_key_bits}")
        print(f"  Mismatched Bits:        {self.mismatched_bits}") 
        print(f"  QBER:                   {qber:.2f}%")
        print(f"  Simulation Duration:    {duration:.3f} seconds") 
        print(f"  Channel Loss Rate:      {avg_loss:.2%}")
        print(f"  Throughput:             {throughput:.2f} bits/sec") 
        print(f"  Classical Messages:     {self.classical_messages}") 
        print(f"  Alice Computation:      {self.computation_time_alice:.6f} s") 
        print(f"  Bob Computation:        {self.computation_time_bob:.6f} s")
        print(f"  Avg Computation/Round:  {avg_computation:.6f} seconds") 
        print("="*60 + "\n")