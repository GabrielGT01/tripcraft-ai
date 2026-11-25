export type TripStatus =
  | "waiting_for_user"
  | "finished";

export type InterruptType =
  | "clarify"
  | "decision";

export interface FlightDetails {
  origin?: string | null;
  destination?: string | null;
  departure_date?: string | null;
  return_date?: string | null;
  trip_type?:
    | "one_way"
    | "round_trip"
    | "unknown";
}

export interface TravelDetails {
  flight?: FlightDetails | null;
  adults?: number;
  budget_amount?: number | null;
  budget_currency?: string | null;
  nationality?: string | null;
  hotel_preferences?: string | null;
  interests?: string[];
}

export interface ClarifyInterrupt {
  question?: string;
  missing?: string[];
  error?: string;
}

export interface DecisionInterrupt {
  presentation?: string;
  question?: string;
  options?: Record<string, string>;
  error?: string;
}

export interface TripResponse {
  thread_id: string;
  status: TripStatus;
  interrupt_type?: InterruptType;
  interrupt?:
    | ClarifyInterrupt
    | DecisionInterrupt;
  travel_details?: TravelDetails | null;
  plan?: string | null;
  saved_filename?: string | null;
  saved_file?: string | null;
  saved_file_content?: string | null;
}

export type ResumePayload = {
  action?:
    | "approve"
    | "revise"
    | "inquire";
  message?: string;
};
