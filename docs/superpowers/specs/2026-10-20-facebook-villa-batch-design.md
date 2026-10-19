# Facebook Villa Batch Publication — Design

## Goal

Publish the verified Facebook Marketplace villa candidates to the Cozy Asia small Telegram channel through the existing Telethon/MTProto production path, without touching older publications or booking/payment workflows.

## Scope

The batch contains the 11 candidate listings selected during the Facebook search. Each listing is represented by its Facebook URL, title, district, four-bedroom facts, price as advertised, seller/profile URL, and a local photo manifest. Listings with confirmed mismatches (sales, three bedrooms, Koh Phangan, or clearly unavailable dates) are excluded.

## Architecture

A new one-shot, data-driven publisher will be added to `Cozyasia/Cozyasia_villas`. It will use the existing `mtproto_user_client`, `channel_publication_policy`, `publication_safety`, and `cozy_catalog` modules. A batch manifest will drive caption generation, photo validation, duplicate detection, album publication, and read-back verification.

The job will target `@arenda_vill_samui`, use the small-channel bot CTA `@Cozyasia_villa_bot`, preserve custom emoji/premium formatting through the existing upgrade path, and use a gated environment flag so normal service startup cannot publish accidentally.

## Safety and invariants

- Never publish a listing without a source Facebook URL and exactly four bedrooms in the manifest.
- Never publish more than 10 Telegram photos per listing album.
- Never reuse a Facebook URL already published by the batch.
- Never delete or edit existing channel posts.
- Never book a villa, send money, or store owner contact details in public captions.
- Run dry-run validation before the real one-shot job.
- Verify every published message by reading it back from Telegram and returning its public URL.

## Inputs

The batch manifest will contain the 11 Facebook URLs and seller/profile URLs already collected in the current task. Photos must be downloaded from the corresponding Facebook cards and stored as a package accessible to the Render job; no watermarked images are allowed.

## Outputs

For each successfully published listing: lot ID with the small-channel `V` prefix, Telegram message ID, public Telegram URL, photo count, and source Facebook URL. Failures are isolated per listing and do not cause an already-published listing to be duplicated on retry.
