import random
import numpy as np
import netsquid as ns
import netsquid.qubits.operators as ops  
from netsquid.protocols import NodeProtocol

class EveProtocol(NodeProtocol):
    """
    Protocollo per il nodo intermedio di Eve.
    Intercetta i qubit che transitano sul canale, effettua una misura Intercept-Resend
    nella base scelta casualmente (se l'attacco è attivo), e poi li ritrasmette verso Bob.
    """
    def __init__(self, node, active=False):
        super().__init__(node)

        # Flag che indica se l'attacco è attivo oppure no
        self.active = active

    def run(self):
        # Porte quantistiche del nodo di Eve, da sorgente a Eve e da Eve a Bob
        port_in = self.node.ports["qubit_in"]
        port_out = self.node.ports["qubit_out"]
        
        while True:
            # Eve resta in ascolto finché non arrivano qubit
            yield self.await_port_input(port_in)
            qubits = port_in.rx_input().items
            
            # Se l'attacco è attivo, Eve intercetta e misura i qubit
            if self.active:
                print(f"[Eve] Attack active in the intermediate node! Intercepting {len(qubits)} qubits in transit...")
                for q in qubits:
                    if q is not None:
                        # Eve sceglie una base a caso tra quelle di Bob
                        basis = random.choice([0, 1, 2])

                        # Converte la base in un angolo di rotazione
                        if basis == 0:
                            angle = -np.pi/4
                        elif basis == 1:
                            angle = -np.pi/2
                        elif basis == 2:
                            angle = -3*np.pi/4
                            
                        # Ruota il qubit nella base scelta
                        rot_op = ops.create_rotation_op(angle, rotation_axis=(0, 1, 0))
                        ns.qubits.operate(q, rot_op)

                        # Misura il qubit (collassa lo stato)
                        ns.qubits.measure(q)

                        # Applica la rotazione inversa per "ricostruire" il qubit
                        inv_rot_op = ops.create_rotation_op(-angle, rotation_axis=(0, 1, 0))
                        ns.qubits.operate(q, inv_rot_op)
            
            # Invia i qubit (alterati o intatti) verso Bob
            port_out.tx_output(qubits)