// The effects of the chain, in their first order. To add an effect: write a file like saturator.js and add it here.
import saturator from './saturator.js';
import eq from './eq.js';
import reverb from './reverb.js';
import ringmod from './ringmod.js';

export const EFFECTS = [saturator, eq, reverb, ringmod];
