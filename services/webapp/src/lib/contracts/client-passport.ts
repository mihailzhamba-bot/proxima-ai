/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
/**
 * Per-tenant cabinet parameters for signal personalization (PMM-21). Threshold values are per-client overrides; global starting defaults live in Policy Layer config and are calibrated by PMM-35 (OQ-1/OQ-4). Versioned by effective_from; additive-only evolution.
 */
export interface ClientPassportV1 {
  schema_version: 1;
  passport_id: string;
  tenant_id: string;
  effective_from: string;
  timezone: 'Europe/Moscow';
  /**
   * Sales drop vs baseline (percent) that triggers SCN-001; global starting default 20, calibrated by PMM-35 (OQ-4).
   */
  sales_drop_threshold_pct: number;
  days_cover_threshold_days: number;
  /**
   * Tenant-level default full replenishment lead time; per-SKU override lives in products.csv. Policy Layer orients: ~60 days production in China up to 4 months complex goods (status: external reference).
   */
  lead_time_days: number;
  safety_buffer_days: number;
  cogs_status: 'complete' | 'top_sku' | 'missing';
  /**
   * @maxItems 64
   */
  priority_categories: string[];
  /**
   * @maxItems 256
   */
  warehouses: string[];
  /**
   * Stored since v1 (decision No. 29); weekend skip behavior is out of W1 scope.
   */
  weekend_days: ('mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun')[];
  /**
   * @maxItems 16
   */
  contacts:
    | []
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ]
    | [
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        },
        {
          role: 'owner' | 'manager';
          channel: 'telegram' | 'email';
          value: string;
        }
      ];
}

