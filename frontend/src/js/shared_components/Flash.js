import React from 'react'
export default class Flash extends React.Component {
  render() {

    if(!this.props.messages || !this.props.type){
      return null;
    }

    const messages = this.props.messages.map((message, i) =>
          <p className='marg-bott-sm fw-5' key={i}>{message.msg}</p>
    );
    return (
      <div {...this.props} className={"sk-flash flash-" + this.props.type + " " + this.props.className}>
        <div style={{marginBottom: '-5px'}}>
          {messages}
        </div>
      </div>
    );
  }
}
