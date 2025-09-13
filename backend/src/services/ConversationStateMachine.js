export class ConversationStateMachine {
  constructor() {
    this.states = {
      GREETING: 'greeting',
      INTENT_RECOGNITION: 'intent_recognition', 
      IDENTITY_VERIFICATION: 'identity_verification',
      DATE_OF_BIRTH: 'date_of_birth',
      PRESCRIPTION_REVIEW: 'prescription_review',
      PRESCRIPTION_SELECTION: 'prescription_selection',
      INTERACTION_CHECK: 'interaction_check',
      CONFIRMATION: 'confirmation',
      COMPLETED: 'completed',
      ERROR: 'error'
    };

    this.transitions = {
      [this.states.GREETING]: {
        refill: this.states.IDENTITY_VERIFICATION,
        question: this.states.INTENT_RECOGNITION,
        greeting: this.states.INTENT_RECOGNITION,
        unclear: this.states.INTENT_RECOGNITION
      },
      [this.states.INTENT_RECOGNITION]: {
        refill: this.states.IDENTITY_VERIFICATION,
        question: this.states.IDENTITY_VERIFICATION, // Still need to verify identity
        greeting: this.states.IDENTITY_VERIFICATION,
        unclear: this.states.INTENT_RECOGNITION
      },
      [this.states.IDENTITY_VERIFICATION]: {
        name_provided: this.states.DATE_OF_BIRTH,
        unclear: this.states.IDENTITY_VERIFICATION,
        error: this.states.ERROR
      },
      [this.states.DATE_OF_BIRTH]: {
        dob_provided: this.states.PRESCRIPTION_REVIEW,
        patient_verified: this.states.PRESCRIPTION_REVIEW,
        patient_not_found: this.states.ERROR,
        unclear: this.states.DATE_OF_BIRTH,
        error: this.states.ERROR
      },
      [this.states.PRESCRIPTION_REVIEW]: {
        prescriptions_found: this.states.PRESCRIPTION_SELECTION,
        no_prescriptions: this.states.ERROR,
        error: this.states.ERROR
      },
      [this.states.PRESCRIPTION_SELECTION]: {
        prescription_selected: this.states.INTERACTION_CHECK,
        unclear: this.states.PRESCRIPTION_SELECTION,
        no_refills: this.states.ERROR,
        expired: this.states.ERROR
      },
      [this.states.INTERACTION_CHECK]: {
        no_interactions: this.states.CONFIRMATION,
        interactions_found: this.states.ERROR,
        check_complete: this.states.CONFIRMATION
      },
      [this.states.CONFIRMATION]: {
        confirmed: this.states.COMPLETED,
        cancelled: this.states.GREETING,
        error: this.states.ERROR
      },
      [this.states.COMPLETED]: {
        new_request: this.states.GREETING,
        goodbye: this.states.COMPLETED
      },
      [this.states.ERROR]: {
        retry: this.states.GREETING,
        new_request: this.states.GREETING,
        goodbye: this.states.COMPLETED
      }
    };
  }

  transition(currentState, event, context = {}) {
    const possibleTransitions = this.transitions[currentState];
    
    if (!possibleTransitions) {
      console.warn(`No transitions defined for state: ${currentState}`);
      return { state: this.states.ERROR, action: 'error_no_transitions' };
    }

    const nextState = possibleTransitions[event];
    
    if (!nextState) {
      console.warn(`No transition for event '${event}' in state '${currentState}'`);
      // Stay in current state for unclear inputs, go to error for other issues
      return { 
        state: event === 'unclear' ? currentState : this.states.ERROR, 
        action: 'stay_or_error' 
      };
    }

    // Determine the action based on the transition
    const action = this.getActionForTransition(currentState, nextState, event, context);
    
    return {
      state: nextState,
      action,
      context: this.updateContext(currentState, nextState, event, context)
    };
  }

  getActionForTransition(fromState, toState, event, context) {
    // Define actions based on state transitions
    const actionMap = {
      [`${this.states.GREETING}->${this.states.IDENTITY_VERIFICATION}`]: 'request_name',
      [`${this.states.INTENT_RECOGNITION}->${this.states.IDENTITY_VERIFICATION}`]: 'request_name',
      [`${this.states.IDENTITY_VERIFICATION}->${this.states.DATE_OF_BIRTH}`]: 'request_dob',
      [`${this.states.DATE_OF_BIRTH}->${this.states.PRESCRIPTION_REVIEW}`]: 'verify_patient',
      [`${this.states.PRESCRIPTION_REVIEW}->${this.states.PRESCRIPTION_SELECTION}`]: 'list_prescriptions',
      [`${this.states.PRESCRIPTION_SELECTION}->${this.states.INTERACTION_CHECK}`]: 'check_interactions',
      [`${this.states.INTERACTION_CHECK}->${this.states.CONFIRMATION}`]: 'process_refill',
      [`${this.states.CONFIRMATION}->${this.states.COMPLETED}`]: 'complete_refill',
      [`${this.states.COMPLETED}->${this.states.GREETING}`]: 'start_new_conversation',
      [`${this.states.ERROR}->${this.states.GREETING}`]: 'restart_conversation'
    };

    const transitionKey = `${fromState}->${toState}`;
    return actionMap[transitionKey] || 'continue';
  }

  updateContext(fromState, toState, event, context) {
    const updatedContext = { ...context };

    // Update context based on the transition
    switch (toState) {
      case this.states.DATE_OF_BIRTH:
        if (context.patientName) {
          updatedContext.awaitingDOB = true;
        }
        break;
        
      case this.states.PRESCRIPTION_REVIEW:
        updatedContext.patientVerified = true;
        updatedContext.awaitingDOB = false;
        break;
        
      case this.states.PRESCRIPTION_SELECTION:
        updatedContext.prescriptionsListed = true;
        break;
        
      case this.states.INTERACTION_CHECK:
        updatedContext.prescriptionSelected = true;
        break;
        
      case this.states.CONFIRMATION:
        updatedContext.interactionCheckComplete = true;
        break;
        
      case this.states.COMPLETED:
        updatedContext.refillComplete = true;
        break;
        
      case this.states.ERROR:
        updatedContext.errorOccurred = true;
        updatedContext.errorState = fromState;
        break;
    }

    return updatedContext;
  }

  getStateDescription(state) {
    const descriptions = {
      [this.states.GREETING]: 'Welcoming the patient and determining how to help',
      [this.states.INTENT_RECOGNITION]: 'Understanding what the patient needs',
      [this.states.IDENTITY_VERIFICATION]: 'Collecting patient name for verification',
      [this.states.DATE_OF_BIRTH]: 'Collecting date of birth for identity confirmation',
      [this.states.PRESCRIPTION_REVIEW]: 'Looking up patient prescriptions',
      [this.states.PRESCRIPTION_SELECTION]: 'Helping patient choose which prescription to refill',
      [this.states.INTERACTION_CHECK]: 'Checking for drug interactions',
      [this.states.CONFIRMATION]: 'Processing the refill request',
      [this.states.COMPLETED]: 'Refill completed successfully',
      [this.states.ERROR]: 'Handling an error or issue'
    };

    return descriptions[state] || 'Unknown state';
  }

  getExpectedInput(state) {
    const expectedInputs = {
      [this.states.GREETING]: 'Patient greeting or request for help',
      [this.states.INTENT_RECOGNITION]: 'What the patient needs (refill, question, etc.)',
      [this.states.IDENTITY_VERIFICATION]: 'Patient\'s full name',
      [this.states.DATE_OF_BIRTH]: 'Patient\'s date of birth',
      [this.states.PRESCRIPTION_REVIEW]: 'System processing - no input expected',
      [this.states.PRESCRIPTION_SELECTION]: 'Name of medication to refill',
      [this.states.INTERACTION_CHECK]: 'System processing - no input expected',
      [this.states.CONFIRMATION]: 'Confirmation or cancellation of refill',
      [this.states.COMPLETED]: 'New request or goodbye',
      [this.states.ERROR]: 'Retry request or new conversation'
    };

    return expectedInputs[state] || 'Any input';
  }

  isTerminalState(state) {
    return state === this.states.COMPLETED;
  }

  isErrorState(state) {
    return state === this.states.ERROR;
  }

  canRetry(state) {
    // States where we can ask the user to try again
    return [
      this.states.IDENTITY_VERIFICATION,
      this.states.DATE_OF_BIRTH,
      this.states.PRESCRIPTION_SELECTION,
      this.states.ERROR
    ].includes(state);
  }

  getRetryMessage(state) {
    const retryMessages = {
      [this.states.IDENTITY_VERIFICATION]: 'I didn\'t catch your name clearly. Could you please tell me your full name again?',
      [this.states.DATE_OF_BIRTH]: 'I need your date of birth to verify your identity. Please say it in month, day, year format.',
      [this.states.PRESCRIPTION_SELECTION]: 'I didn\'t understand which medication you\'d like to refill. Could you please tell me the name again?',
      [this.states.ERROR]: 'I apologize for the confusion. Let\'s start over. How can I help you today?'
    };

    return retryMessages[state] || 'Could you please try again?';
  }

  // Method to validate state transitions
  isValidTransition(fromState, toState) {
    const possibleTransitions = this.transitions[fromState];
    return possibleTransitions && Object.values(possibleTransitions).includes(toState);
  }

  // Method to get all possible next states
  getPossibleNextStates(currentState) {
    const transitions = this.transitions[currentState];
    return transitions ? Object.values(transitions) : [];
  }
}

