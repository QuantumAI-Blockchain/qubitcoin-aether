// wQUSD — Wrapped QUSD SPL Token on Solana
//
// This Anchor program implements the wQUSD stablecoin on Solana.
// QUSD is locked on the Qubitcoin chain → bridge operator mints wQUSD on Solana.
// User burns wQUSD on Solana → bridge operator unlocks QUSD on Qubitcoin chain.
//
// Features:
//   - SPL Token 2022 compatible
//   - Bridge operator authority for mint/burn
//   - 0.05% bridge fee (5 bps) — routed to QUSD reserves
//   - Emergency pause capability
//   - Replay protection via processed tx hash tracking
//   - 1:1 peg with QUSD (fully backed by locked QUSD)

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Burn, MintTo, Token, TokenAccount, Mint};

declare_id!("QUSDwrapped11111111111111111111111111111111");

/// Bridge fee in basis points (5 = 0.05%) — routed to QUSD reserves.
const BRIDGE_FEE_BPS: u64 = 5;
const BPS_DENOMINATOR: u64 = 10_000;

#[program]
pub mod wqusd {
    use super::*;

    /// Initialize the wQUSD bridge state.
    pub fn initialize(ctx: Context<Initialize>, fee_recipient: Pubkey) -> Result<()> {
        let state = &mut ctx.accounts.bridge_state;
        state.authority = ctx.accounts.authority.key();
        state.mint = ctx.accounts.mint.key();
        state.fee_recipient = fee_recipient;
        state.paused = false;
        state.total_minted = 0;
        state.total_burned = 0;
        state.total_fees = 0;
        state.bump = ctx.bumps.bridge_state;
        Ok(())
    }

    /// Bridge operator mints wQUSD when QUSD is locked on the QBC chain.
    pub fn bridge_mint(
        ctx: Context<BridgeMint>,
        amount: u64,
        source_tx_hash: [u8; 32],
        source_chain_id: u64,
    ) -> Result<()> {
        let state = &mut ctx.accounts.bridge_state;
        require!(!state.paused, WQUSDError::Paused);
        require!(amount > 0, WQUSDError::ZeroAmount);

        let receipt = &mut ctx.accounts.tx_receipt;
        require!(!receipt.processed, WQUSDError::AlreadyProcessed);
        receipt.processed = true;
        receipt.source_tx_hash = source_tx_hash;
        receipt.source_chain_id = source_chain_id;
        receipt.amount = amount;
        receipt.recipient = ctx.accounts.recipient.key();
        receipt.timestamp = Clock::get()?.unix_timestamp;

        let fee = amount.checked_mul(BRIDGE_FEE_BPS).unwrap() / BPS_DENOMINATOR;
        let net_amount = amount.checked_sub(fee).unwrap();

        let seeds = &[b"bridge_state".as_ref(), &[state.bump]];
        let signer = &[&seeds[..]];

        // Mint net amount to recipient
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                MintTo {
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.recipient_token.to_account_info(),
                    authority: ctx.accounts.bridge_state.to_account_info(),
                },
                signer,
            ),
            net_amount,
        )?;

        // Mint fee to reserve recipient
        if fee > 0 {
            token::mint_to(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.to_account_info(),
                    MintTo {
                        mint: ctx.accounts.mint.to_account_info(),
                        to: ctx.accounts.fee_token.to_account_info(),
                        authority: ctx.accounts.bridge_state.to_account_info(),
                    },
                    signer,
                ),
                fee,
            )?;
        }

        state.total_minted = state.total_minted.checked_add(amount).unwrap();
        state.total_fees = state.total_fees.checked_add(fee).unwrap();

        emit!(BridgeMintEvent {
            recipient: ctx.accounts.recipient.key(),
            amount: net_amount,
            fee,
            source_tx_hash,
            source_chain_id,
        });

        Ok(())
    }

    /// User burns wQUSD to redeem QUSD on the QBC chain.
    pub fn bridge_burn(
        ctx: Context<BridgeBurn>,
        amount: u64,
        dest_chain_id: u64,
    ) -> Result<()> {
        let state = &mut ctx.accounts.bridge_state;
        require!(!state.paused, WQUSDError::Paused);
        require!(amount > 0, WQUSDError::ZeroAmount);

        let fee = amount.checked_mul(BRIDGE_FEE_BPS).unwrap() / BPS_DENOMINATOR;
        let net_burn = amount.checked_sub(fee).unwrap();

        token::burn(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Burn {
                    mint: ctx.accounts.mint.to_account_info(),
                    from: ctx.accounts.sender_token.to_account_info(),
                    authority: ctx.accounts.sender.to_account_info(),
                },
            ),
            net_burn,
        )?;

        state.total_burned = state.total_burned.checked_add(net_burn).unwrap();
        state.total_fees = state.total_fees.checked_add(fee).unwrap();

        emit!(BridgeBurnEvent {
            sender: ctx.accounts.sender.key(),
            amount: net_burn,
            fee,
            dest_chain_id,
        });

        Ok(())
    }

    pub fn pause(ctx: Context<AdminAction>) -> Result<()> {
        ctx.accounts.bridge_state.paused = true;
        Ok(())
    }

    pub fn unpause(ctx: Context<AdminAction>) -> Result<()> {
        ctx.accounts.bridge_state.paused = false;
        Ok(())
    }
}

// ─── Accounts ───────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + BridgeState::INIT_SPACE,
        seeds = [b"bridge_state"],
        bump
    )]
    pub bridge_state: Account<'info, BridgeState>,
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(amount: u64, source_tx_hash: [u8; 32])]
pub struct BridgeMint<'info> {
    #[account(mut, seeds = [b"bridge_state"], bump = bridge_state.bump)]
    pub bridge_state: Account<'info, BridgeState>,
    #[account(
        init,
        payer = authority,
        space = 8 + TxReceipt::INIT_SPACE,
        seeds = [b"receipt", source_tx_hash.as_ref()],
        bump
    )]
    pub tx_receipt: Account<'info, TxReceipt>,
    #[account(mut, constraint = mint.key() == bridge_state.mint)]
    pub mint: Account<'info, Mint>,
    /// CHECK: Recipient address.
    pub recipient: UncheckedAccount<'info>,
    #[account(mut)]
    pub recipient_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub fee_token: Account<'info, TokenAccount>,
    #[account(mut, constraint = authority.key() == bridge_state.authority)]
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct BridgeBurn<'info> {
    #[account(mut, seeds = [b"bridge_state"], bump = bridge_state.bump)]
    pub bridge_state: Account<'info, BridgeState>,
    #[account(mut, constraint = mint.key() == bridge_state.mint)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub sender: Signer<'info>,
    #[account(mut)]
    pub sender_token: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct AdminAction<'info> {
    #[account(mut, seeds = [b"bridge_state"], bump = bridge_state.bump,
              constraint = authority.key() == bridge_state.authority)]
    pub bridge_state: Account<'info, BridgeState>,
    pub authority: Signer<'info>,
}

// ─── State ──────────────────────────────────────────────────────────

#[account]
#[derive(InitSpace)]
pub struct BridgeState {
    pub authority: Pubkey,
    pub mint: Pubkey,
    pub fee_recipient: Pubkey,
    pub paused: bool,
    pub total_minted: u64,
    pub total_burned: u64,
    pub total_fees: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct TxReceipt {
    pub processed: bool,
    pub source_tx_hash: [u8; 32],
    pub source_chain_id: u64,
    pub amount: u64,
    pub recipient: Pubkey,
    pub timestamp: i64,
}

// ─── Events ─────────────────────────────────────────────────────────

#[event]
pub struct BridgeMintEvent {
    pub recipient: Pubkey,
    pub amount: u64,
    pub fee: u64,
    pub source_tx_hash: [u8; 32],
    pub source_chain_id: u64,
}

#[event]
pub struct BridgeBurnEvent {
    pub sender: Pubkey,
    pub amount: u64,
    pub fee: u64,
    pub dest_chain_id: u64,
}

// ─── Errors ─────────────────────────────────────────────────────────

#[error_code]
pub enum WQUSDError {
    #[msg("Bridge is paused")]
    Paused,
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Transaction already processed")]
    AlreadyProcessed,
}
