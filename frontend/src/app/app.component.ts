import { Component } from '@angular/core';
import { ChatService } from './services/chat.service';

interface GameEvidence {
  table: 'game_details';
  id: number;
  home_team: string;
  away_team: string;
  home_points: number;
  away_points: number;
  game_date: string;
  display_name: string;
}

interface PlayerEvidence {
  table: 'player_box_scores';
  id: string;
  player_name: string;
  team: string;
  points: number;
  rebounds?: number;
  assists?: number;
  game_id: number;
  display_name: string;
}

type Evidence = GameEvidence | PlayerEvidence;

interface Message {
  sender: 'user' | 'bot';
  text: string;
  evidence?: Evidence[];
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'AI Engineering Sandbox';
  messages: Message[] = [];
  userInput = '';
  expandedEvidence: { [key: string]: boolean } = {};

  constructor(private chatService: ChatService) { }

  sendMessage(): void {
    const input = this.userInput.trim();
    if (!input) {
      return;
    }
    this.messages.push({ sender: 'user', text: input });
    this.userInput = '';

    this.chatService.sendMessage(input).subscribe({
      next: (res: any) => {
        const reply = res?.answer ?? 'No Answer.';
        this.messages.push({
          sender: 'bot',
          text: reply,
          evidence: res?.evidence || []
        });
      },
      error: () => {
        this.messages.push({ sender: 'bot', text: 'Error contacting server.' });
      }
    });
  }

  toggleEvidence(key: string): void {
    this.expandedEvidence[key] = !this.expandedEvidence[key];
  }
}