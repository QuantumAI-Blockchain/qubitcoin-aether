use pqcrypto_dilithium::dilithium5;
use pqcrypto_traits::sign::{DetachedSignature, PublicKey, SecretKey};
use std::env;
use std::io::Read;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage:");
        eprintln!("  dilithium-helper keygen");
        eprintln!("  dilithium-helper sign <sk_hex> <message_hex>");
        eprintln!("  dilithium-helper verify <pk_hex> <message_hex> <sig_hex>");
        std::process::exit(1);
    }

    match args[1].as_str() {
        "keygen" => {
            let (pk, sk) = dilithium5::keypair();
            println!("PK={}", hex::encode(pk.as_bytes()));
            println!("SK={}", hex::encode(sk.as_bytes()));
            eprintln!("pk_size={} sk_size={}", pk.as_bytes().len(), sk.as_bytes().len());
        }
        "sign" => {
            if args.len() < 4 {
                eprintln!("Usage: dilithium-helper sign <sk_hex> <message_hex>");
                std::process::exit(1);
            }
            let sk_bytes = hex::decode(&args[2]).expect("invalid sk hex");
            let msg_bytes = hex::decode(&args[3]).expect("invalid message hex");
            let sk = dilithium5::SecretKey::from_bytes(&sk_bytes).expect("invalid sk");
            let sig = dilithium5::detached_sign(&msg_bytes, &sk);
            println!("SIG={}", hex::encode(sig.as_bytes()));
            eprintln!("sig_size={}", sig.as_bytes().len());
        }
        "verify" => {
            if args.len() < 5 {
                eprintln!("Usage: dilithium-helper verify <pk_hex> <message_hex> <sig_hex>");
                std::process::exit(1);
            }
            let pk_bytes = hex::decode(&args[2]).expect("invalid pk hex");
            let msg_bytes = hex::decode(&args[3]).expect("invalid message hex");
            let sig_bytes = hex::decode(&args[4]).expect("invalid sig hex");
            let pk = dilithium5::PublicKey::from_bytes(&pk_bytes).expect("invalid pk");
            let sig = dilithium5::DetachedSignature::from_bytes(&sig_bytes).expect("invalid sig");
            match dilithium5::verify_detached_signature(&sig, &msg_bytes, &pk) {
                Ok(()) => println!("VALID"),
                Err(_) => println!("INVALID"),
            }
        }
        _ => {
            eprintln!("Unknown command: {}", args[1]);
            std::process::exit(1);
        }
    }
}
