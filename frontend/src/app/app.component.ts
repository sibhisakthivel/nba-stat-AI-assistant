import { Component } from '@angular/core';
import { ChatService } from './services/chat.service';

interface Evidence {
  table: string;
  id: number | string;
}

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
  expandedEvidence: { [key: number]: boolean } = {};

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

  toggleEvidence(index: number): void {
    this.expandedEvidence[index] = !this.expandedEvidence[index];
  }
}